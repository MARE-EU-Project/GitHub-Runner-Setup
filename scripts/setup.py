"""Interactive local configuration; all server changes remain Ansible-managed."""

import argparse
import configparser
import getpass
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

import yaml


def ask(label, default="", pattern=None):
    while True:
        value = input(f"{label}" + (f" [{default}]" if default else "") + ": ").strip() or default
        if value and (pattern is None or re.fullmatch(pattern, value)):
            return value
        print("Please enter a valid value.")


def yes(label, default=False):
    while True:
        value = input(f"{label} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
        if not value:
            return default
        if value in ("y", "yes", "n", "no"):
            return value in ("y", "yes")


def read_yaml(path):
    value = yaml.safe_load(path.read_text()) if path.exists() else {}
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Expected a YAML mapping in {path}; edit it with Vim first.")
    return value


def write_private(path, content):
    """Publish atomically, without leaving a partially written configuration."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            output.write(content.encode())
            output.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def configure(args, bin_dir):
    directory = args.inventory.parent
    source = Path("DATA/etc/ansible/templates")
    directory.mkdir(parents=True, exist_ok=True)
    shared = directory / "group_vars/all.yml"
    if not shared.exists():
        shared.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / "group_vars/all.yml", shared)
    if not args.config.exists():
        config = configparser.ConfigParser(interpolation=None)
        config.read(source / "ansible.cfg")
        config["defaults"]["inventory"] = str(args.inventory.resolve())
        config["defaults"]["roles_path"] = str(Path("DATA/etc/ansible/roles").resolve())
        args.config.parent.mkdir(parents=True, exist_ok=True)
        with args.config.open("x") as output:
            config.write(output)
    os.environ["ANSIBLE_CONFIG"] = str(args.config.resolve())

    existing = {}
    if args.inventory.exists():
        # Resolve Ansible inheritance; never display host variables or secrets.
        result = run([str(bin_dir / "ansible-inventory"), "-i", str(args.inventory), "--list"],
                     capture_output=True, text=True)
        inventory = json.loads(result.stdout)
        pending, visited, hosts = ["github_runners"], set(), set()
        while pending:
            group = pending.pop()
            if group in visited:
                continue
            visited.add(group)
            hosts.update(inventory.get(group, {}).get("hosts", []))
            pending.extend(inventory.get(group, {}).get("children", []))
        variables = inventory.get("_meta", {}).get("hostvars", {})
        existing = {host: variables.get(host, {}) for host in sorted(hosts)}
        if not existing:
            raise ValueError("Inventory has no hosts under github_runners. Edit it with Vim first.")
        print("Existing inventory hosts: " + ", ".join(sorted(existing)))
        print("Select a host below. Existing values are preserved; use Vim to change them.")

    alias = args.limit or ask("Inventory host name", next(iter(existing)) if len(existing) == 1 else "",
                              r"[A-Za-z_][A-Za-z0-9_]*")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", alias):
        raise ValueError("Setup requires one inventory host name, not a LIMIT pattern.")
    if args.inventory.exists() and alias not in existing:
        raise ValueError("Host not found. Add it with Vim or use a separate INVENTORY_DIR for a new host.")

    host_file = directory / "host_vars" / f"{alias}.yml"
    values = read_yaml(host_file)
    effective = existing.get(alias, {})
    before = yaml.safe_dump(values)

    def missing(key, label, default, pattern=None):
        if not effective.get(key):
            values[key] = ask(label, default, pattern)
        return effective.get(key) or values[key]

    address = missing("ansible_host", "SSH hostname or IP", alias, r"[A-Za-z0-9][A-Za-z0-9.:-]*")
    user = missing("ansible_user", "SSH administrator (sudo-capable)", getpass.getuser(), r"[a-z_][a-z0-9_-]*")
    organization = missing("github_organization", "GitHub organization", "MARE-EU-Project", r"[A-Za-z0-9][A-Za-z0-9-]*")
    group = ask("Existing GitHub runner group", effective.get("github_runner_group") or "")
    if group != effective.get("github_runner_group"):
        values["github_runner_group"] = group
    instances = effective.get("runner_instances")
    if not instances:
        name = ask("Unique GitHub runner name", alias.replace("_", "-"), r"[a-z][a-z0-9-]{0,40}")
        account = ask("Dedicated runner account", "ghrunner", r"[a-z_][a-z0-9_-]{0,30}")
        if account in (user, "root", "ubuntu", "runner", "nobody"):
            raise ValueError("Use a dedicated runner account, distinct from the SSH administrator.")
        instances = [{"name": name, "user": account,
                      "install_dir": f"/opt/actions-runner/{name}",
                      "work_dir": f"/var/lib/actions-runner/{name}", "labels": [name, "mare-smoke"],
                      "minikube_profile": name}]
        values["runner_instances"] = instances
        for key, label in (("docker_enabled", "Install Docker and Compose?"),
                           ("kubernetes_enabled", "Install kubectl, Minikube and Helm?"),
                           ("virtualization_enabled", "Install Vagrant/libvirt (requires usable KVM)?"),
                           ("wasmtime_enabled", "Install Wasmtime?")):
            values[key] = yes(label, True)
    configured = {**effective, **values}
    initialize = bool(configured.get("kubernetes_enabled", True) and configured.get("minikube_enabled", True)) and yes(
        "Initialize the configured Minikube cluster(s)?", True)
    if initialize and configured.get("minikube_driver", "docker") == "docker" and not configured.get("docker_enabled", True):
        raise ValueError("Minikube's Docker driver requires Docker. Enable Docker or decline cluster initialization.")
    if initialize != effective.get("minikube_initialize"):
        values["minikube_initialize"] = initialize
    if before != yaml.safe_dump(values):
        write_private(host_file, yaml.safe_dump(values, sort_keys=False))
    if not args.inventory.exists():
        # GitHub names can contain spaces/hyphens; Ansible group identifiers cannot.
        inventory_group = re.sub(r"[^A-Za-z0-9_]", "_", group)
        if inventory_group[0].isdigit():
            inventory_group = "group_" + inventory_group
        if inventory_group in ("all", "ungrouped", "github_runners", alias):
            inventory_group = "group_" + inventory_group
        runners = {"children": {inventory_group: {"hosts": {alias: {}}}}}
        inventory = {"all": {"children": {"github_runners": runners}}}
        write_private(args.inventory, yaml.safe_dump(inventory, sort_keys=False))

    print(f"\nTarget: {alias} ({user}@{address})")
    print(f"GitHub: {organization} / {group}")
    print("Runners: " + ", ".join(f"{item['name']} as {item['user']}" for item in instances))
    print(f"Configuration: {args.inventory} and {host_file}")
    print(f"Review tool switches and pins in {shared}.")
    print(f"GitHub group {group!r} must already be restricted to your approved private repositories.")
    ssh = ["ssh", "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=ask",
           "-o", "PasswordAuthentication=no", "-o", "KbdInteractiveAuthentication=no",
           "-p", str(effective.get("ansible_port", 22))]
    if effective.get("ansible_ssh_private_key_file"):
        ssh += ["-i", str(Path(effective["ansible_ssh_private_key_file"]).expanduser())]
    return alias, ssh + ["-l", user, address, "true"]


def credentials(args, bin_dir):
    if not yes("Create/refresh the registration token in Vault?", not args.vault.exists()):
        return
    print("Get a fresh organization registration token from GitHub Settings → Actions → Runners")
    print("→ New self-hosted runner. Paste only the token below; no PAT is needed.")
    token = getpass.getpass("Registration token (hidden): ").strip()
    if not token or any(character.isspace() for character in token):
        raise ValueError("A nonempty registration token without whitespace is required.")
    args.vault.parent.mkdir(parents=True, exist_ok=True)
    args.vault.parent.chmod(0o700)
    if args.password_file.exists():
        password = args.password_file.read_text().rstrip("\r\n")
        args.password_file.chmod(0o600)
    else:
        password = getpass.getpass("Vault password (hidden): ")
        if not args.vault.exists() and password != getpass.getpass("Confirm Vault password: "):
            raise ValueError("Vault passwords do not match.")
    if not password or "\n" in password:
        raise ValueError("A nonempty, single-line Vault password is required.")
    # Plaintext token stays in memory and stdin; only a short-lived password file touches disk.
    with tempfile.TemporaryDirectory(dir=args.vault.parent) as temporary:
        password_file = Path(temporary) / "password"
        write_private(password_file, password + "\n")
        vault_command = [str(bin_dir / "ansible-vault")]
        password_args = ["--vault-password-file", str(password_file)]
        content = {}
        if args.vault.exists():
            decrypted = run(vault_command + ["decrypt", "--output", "-"] + password_args + [str(args.vault)],
                            capture_output=True, text=True)
            content = yaml.safe_load(decrypted.stdout)
            if not isinstance(content, dict):
                raise ValueError("Existing Vault must contain a YAML mapping.")
        content["runner_registration_token"] = token
        encrypted = run(vault_command + ["encrypt", "--output", "-"] + password_args,
                        input=yaml.safe_dump(content), capture_output=True, text=True)
        if not encrypted.stdout.startswith("$ANSIBLE_VAULT;"):
            raise ValueError("Vault encryption did not return an encrypted file.")
        write_private(args.vault, encrypted.stdout)
    if not args.password_file.exists() and yes("Save the Vault password locally (0600, gitignored)?"):
        args.password_file.parent.mkdir(parents=True, exist_ok=True)
        args.password_file.parent.chmod(0o700)
        write_private(args.password_file, password + "\n")
    print("Encrypted Vault saved. Existing Vault variables were preserved.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inventory", "config", "vault", "password-file"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--limit", default="")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        raise ValueError("Run task setup in an interactive terminal; use task provision for automation.")
    os.umask(0o077)
    bin_dir = Path(sys.executable).parent
    alias, ssh = configure(args, bin_dir)
    if yes("Check SSH key access and confirm the server host key now?", True):
        run(ssh)
    credentials(args, bin_dir)
    sudo = yes("Does sudo require a password?")
    variables = [f"VENV={bin_dir.parent}", f"INVENTORY={args.inventory}", f"CONFIG={args.config}", f"VAULT_FILE={args.vault}",
                 f"VAULT_PASSWORD_FILE={args.password_file}", f"LIMIT={alias}"]
    if not yes(f"Provision {alias}, then verify it? This installs enabled tools and starts the runner."):
        print("Configuration saved. Continue later with:\n" + shlex.join(["task", "provision"] + variables))
        return
    for task in ("provision", "verify"):
        run(["task", task] + variables + (["--", "--ask-become-pass"] if sudo else []))
    print("Setup and verification completed. Confirm the runner is Idle in GitHub, then run a private-repository job.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled; saved local configuration is retained.", file=sys.stderr)
        sys.exit(130)
    except yaml.YAMLError:
        print("Setup stopped: invalid YAML. Check your local configuration or Vault using Vim.", file=sys.stderr)
        sys.exit(1)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        # Do not render subprocess input/output: Vault commands can contain secrets in memory.
        print(f"Setup stopped: {error}", file=sys.stderr)
        sys.exit(1)
