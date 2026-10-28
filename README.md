# GitHub Actions runner hosts

Reusable Ansible provisioning for persistent **organization-level** runners.
The GitHub organization defaults to [`MARE-EU-Project`](https://github.com/MARE-EU-Project);
the runner group is required configuration, with no fixed default.
Only Ubuntu **24.04 (noble)** and **26.04 (resolute)**,
**x86-64**, are accepted. This project is not a VM image: never clone a
registered runner, its credentials, machine identity, caches, or kubeconfig.

## Local quickstart

Your computer is the Ansible controller; selected inventory hosts receive
changes over SSH. Install Python 3.12+ with venv support, Vim, SSH and
[Task v3.54+](https://taskfile.dev/docs/installation), then run from this checkout:

```console
task setup
```

The guided setup installs the pinned Ansible controller into `.venv`, then:

1. Collects the target hostname/IP, sudo-capable SSH user, GitHub organization,
   existing runner group and unique runner name. The dedicated service account
   defaults to **ghrunner**.
2. Lets you choose Docker/Compose, Kubernetes tools, Vagrant/libvirt and Wasmtime.
   With Kubernetes/Minikube enabled, cluster initialization defaults to **Yes**;
   press Enter to initialize it or answer No to install the tools only.
3. Writes private local configuration under `DATA/etc/ansible/`. A new inventory
   contains only your selected host, under its GitHub group, for example `ENG`.
   Spaces/hyphens are converted to underscores for the Ansible group identifier;
   `github_runner_group` retains the exact GitHub name.
4. Offers an SSH connection check, using SSH's normal host-key confirmation.
   Verify the fingerprint through a trusted channel. Configure SSH key access
   for Ansible; the administrator and runner accounts must be different.
5. Offers hidden prompts for a short-lived organization registration token and
   Vault password. Existing Vault variables are preserved. Saving the password
   locally is optional; it is ignored by Git and restricted to mode `0600`.
6. Shows the target summary and asks before running provisioning followed by
   verification. It prompts for a sudo password if you select that option.

For example, enter `cysec_workbench` as the inventory name,
`runner-private.example.org` as the address, your SSH administrator,
`MARE-EU-Project`, `ENG`, and `cysec-workbench` as the runner name.
The result uses `/opt/actions-runner/cysec-workbench` for installation and
`/var/lib/actions-runner/cysec-workbench` for job work.

Run `task setup` again to select an existing inventory host; its settings are
preserved; the runner group is offered as an editable default on every run.
Other supplied values are not prompted for again. To select
one directly, use `task setup LIMIT=cysec_workbench`. Use Vim to change existing
settings. The wizard accepts one host name, rather than an Ansible limit pattern.
To add another host, edit the inventory/host variables or start a separate
inventory with `task setup INVENTORY_DIR=DATA/etc/ansible/lab`.

The Minikube initialization prompt also appears for existing hosts and defaults
to Yes. Existing managed clusters are verified and reused; they are not recreated.
It saves `minikube_initialize` per host and runs initialization through Ansible.
The normal capacity and profile-ownership checks still apply (defaults: 2 CPUs
and 16000 MB per cluster). Direct `task provision` uses the saved setting;
manual inventories retain `minikube_initialize: false` unless enabled explicitly.

Provisioning uses the existing Ansible playbooks and their maintenance guards;
setup never grants upgrade, reconfiguration, removal or reboot permissions.
It does not create GitHub runner groups or change repository access: keep your selected group
restricted to approved private repositories with public access disabled.
The host must meet the [prerequisites](#controller-and-target-prerequisites)
for the tools you select. After verification, confirm the runner is Idle in
GitHub and run a job from an approved private repository.

Setup is split into two commands, with `task setup` as the combined entry point:

| Command | Purpose |
|---|---|
| `task setup:ansible` | Install the pinned local Ansible controller; no server changes or prompts |
| `task setup:runner` | Configure, provision and verify a runner interactively; ensures Ansible is installed first |
| `task setup` | Run the complete setup through `setup:runner` |

The guided runner setup requires an interactive terminal. For automation or
finer control, use the commands below.

## Manual configuration and daily commands

```console
task setup:ansible           # Install the pinned controller into .venv
task inventory:init          # Create missing local files; preserve your edits
vim DATA/etc/ansible/hosts
vim DATA/etc/ansible/group_vars/all.yml
vim DATA/etc/ansible/host_vars/noble_runner.yml
```

Local files follow Ansible's `/etc/ansible` layout:

```text
DATA/etc/ansible/
├── ansible.cfg
├── hosts
├── group_vars/
│   └── all.yml
├── host_vars/
│   ├── noble_runner.yml
│   └── resolute_runner.yml
├── vault/
│   ├── .gitkeep            # Tracked layout only
│   ├── vault.yml           # Encrypted secrets, ignored
│   └── password            # Optional local Vault password, ignored
├── templates/             # Tracked examples used by initialization and validation
├── playbooks/             # Tracked provisioning and verification entry points
└── roles/                 # Tracked reusable Ansible roles
```

Reusable files under `templates/`, `playbooks/` and `roles/`, plus layout
`.gitkeep` files, are version-controlled. Your active configuration, inventory
and secrets remain gitignored. `task inventory:init` copies missing files from
`templates/`. The generated local `ansible.cfg` is derived from
`templates/ansible.cfg` and uses absolute inventory and role paths; update
those paths if you move the checkout. All Ansible assets are located under `DATA/etc/ansible/`.
Task stores controller temporary files in gitignored `DATA/var/tmp/ansible/`.

Configure a fresh dedicated Ubuntu 24.04 or 26.04 x86-64 host with SSH, sudo
and usable KVM/nested virtualization. Set its address and SSH user in `hosts`:

```yaml
noble_runner:
  ansible_host: runner-private.example.org  # Replace with your target
  ansible_user: provisioner                 # Its sudo-capable SSH user
```

Review versions/switches in `group_vars/all.yml` and use globally unique runner
names and dedicated accounts in `host_vars`. Existing unmanaged runners are
not adopted. Verify the target SSH host key before provisioning.

Set `github_runner_group` in `group_vars/all.yml` for a shared default, or in
`host_vars/<host>.yml` for a host-specific group. `task setup:runner` prompts for
the group and saves your selection per host. For example:

```yaml
github_runner_group: Platform CI
```

Create that group in your GitHub organization before registration. Changing the
group of an already registered runner follows the guarded reconfiguration
procedure; editing this setting alone does not bypass maintenance checks.
`ENG` elsewhere in the examples is only an example group name.

Keep the selected GitHub group restricted to approved private repositories, with
public access disabled. Public repository CI can use GitHub-hosted runners.

Create the encrypted token file with `task vault:create`, or use
`task vault:edit` if it already exists. Both open Vim with swap, backup and
persistent undo disabled. Enter the following YAML, then save with `:wq`:

```yaml
runner_registration_token: "PASTE_THE_SHORT_LIVED_TOKEN_HERE"
```

Obtain a fresh organization registration token from GitHub Settings → Actions →
Runners → New self-hosted runner. It expires after one hour; no PAT is required.
Keep tokens/passwords in Vault and its interactive prompts, outside command
arguments and chat.

To keep the Vault password locally, use Vim without swap, backup or undo files:

```console
umask 077
mkdir -p DATA/etc/ansible/vault
chmod 0700 DATA/etc/ansible/vault
vim -n -i NONE -u NONE --cmd "set nobackup nowritebackup noundofile" DATA/etc/ansible/vault/password
chmod 0600 DATA/etc/ansible/vault/password
```

Enter only the Vault password on one line. Both `vault.yml` and `password` are
gitignored; only `.gitkeep` is tracked. Task loads the Vault as extra variables
for targeted playbooks, using the password file when present and prompting
otherwise. `task inventory` and `task validate` do not load secrets.
The encrypted Vault and its password together grant access to its contents;
keep this directory owner-only and outside shared backups.

```console
task validate                       # Syntax-check all three playbooks; no SSH
task inventory                      # Target-host/group graph; no secrets needed
task check LIMIT=noble_runner        # Check-mode preview; see its limitations below
task provision LIMIT=noble_runner    # Install tools, register and start the runner
task verify LIMIT=noble_runner       # Account/service/tool checks
task provision LIMIT=noble_runner    # Repeat: expect changed=0 once converged
```

Retain recaps and confirm the runner is Idle in your selected group. Repeat for
`LIMIT=resolute_runner` after configuring that host. Routed acceptance uses an
approved private repository. Functional workloads, Minikube initialization and
maintenance retain their explicit opt-ins.

Run `task` to list commands. Remote playbooks require `LIMIT`; append
`-- --ask-become-pass` if sudo needs a password. Arguments after `--` are
forwarded individually to Ansible; keep secrets out of them, including `-e`.

| Variable | Default |
|---|---|
| `INVENTORY_DIR` | `DATA/etc/ansible` |
| `INVENTORY` | `<INVENTORY_DIR>/hosts` |
| `CONFIG` | `<INVENTORY_DIR>/ansible.cfg` |
| `VAULT_FILE` | `<INVENTORY_DIR>/vault/vault.yml` |
| `VAULT_PASSWORD_FILE` | `<INVENTORY_DIR>/vault/password` |
| `VAULT_ARGS` | Uses the local password file if present; otherwise prompts when needed |
| `VENV` | Repository `.venv`; no activation needed |

For a separate inventory, use `INVENTORY_DIR=DATA/etc/ansible/lab` consistently
with initialization and subsequent commands. Initialization fills only missing
files.

## Safety and validation status

**Full provisioning and registration passed on Ubuntu 24.04 and 26.04.**
The production `cysec-workbench` runner was subsequently reinstalled through
Ansible and validated with a GitHub-dispatched private-repository job, including
the hardened account/service and all six runtime functional checks.
The 2026-10-27/28 runs
covered zero-change provisioning repeats, service/account permissions, tool
versions, Docker/Compose, Minikube/Kubernetes/Helm, nested Vagrant/libvirt guests
and WASI execution. Separate tool/runtime and registration runs are documented
in local acceptance reports; see [evidence retention](#acceptance-evidence-to-retain).

The exact smoke script also passed locally as each runner account.
Test registrations/resources were removed. Existing host workloads were
preserved during the production runner replacement. KVM acceptance requires physical hosts
or VMs exposing nested virtualization.

Requested versions are requirements, **not evidence that a release exists**.
Missing packages, upstream artifacts, checksums, or incompatible dependencies
are hard failures; there is no fallback to another release or `latest`.
Review the version/source notes below before running the example unchanged.
Do not use production hosts for initial acceptance.

Provisioning does not prune Docker, change Docker daemon configuration, delete
Minikube profiles, or remove libvirt workloads. Explicit runner removal is a
separate playbook. Functional tests are off by default and require two opt-ins.
Maintenance and reboot permissions are also off by default.

## Controller and target prerequisites

* Controller: Linux, Python 3.12+, **ansible-core 2.21.x** (development controller:
  2.21.5). Only the included `ansible.builtin` collection is required.
  Pin controller packages in your controller
  environment; review upstream advisories before changing them.
* Targets: supported Ubuntu release, Python 3, SSH, systemd, a sudo-capable
  provisioning account, working DNS, correct time, CA trust and outbound HTTPS
  to GitHub and the documented software publishers. Host-key checking stays on.
  Supply a sudo password through a prompt/Vault if required. Provisioning installs
  Ubuntu's `python3-pip` and `python3-venv` through the guarded package installer.
  Keep project dependencies in virtual environments (`python3 -m venv .venv`);
  do not install them into Ubuntu's externally managed system Python.
* KVM: CPU `vmx` or `svm`, usable `/dev/kvm`, and firmware virtualization enabled.
  In a VM, the hypervisor must expose virtualization extensions and nested KVM.
  Enable nesting on the **outer host**, not by weakening target permissions.
  Containerized target testing cannot prove this.
* Minikube defaults reserve 2 CPUs and 16000 MB **per initialized profile**,
  plus 2048 MB host memory reserve. Budget additional resources for Docker jobs,
  guest VMs, filesystem space, image downloads, and concurrent runners.
  Use SSD storage and size the host for the aggregate workload, not just one job.
* Package operations can affect host services. Drain every runner sharing the
  host before enabling upgrades or starting maintenance.

No firewall rules, host security controls, world-writable KVM devices, or
unrestricted passwordless sudo are installed. Ubuntu's ordinary `sudo` package
supports Ansible's scoped escalation; runner accounts are not sudoers.

## Project layout

| Path | Responsibility |
|---|---|
| `DATA/etc/ansible/roles/preflight` | Read-only platform, identity, virtualization and reboot checks |
| `DATA/etc/ansible/roles/tools` | Release-aware packages, verified binaries, account permissions, optional Minikube |
| `DATA/etc/ansible/roles/runner` | Owned installations, GitHub registration, systemd, guarded maintenance/removal |
| `DATA/etc/ansible/roles/verification` | Versions, services, account access, inventory and opt-in runtime tests |
| `DATA/etc/ansible/templates` | Two release groups, shared `group_vars`, per-host instances |
| `DATA/etc/ansible/playbooks/provision.yml` | Install tools and runners, optionally initialize Minikube |
| `DATA/etc/ansible/playbooks/verify.yml` | Verify, optionally run isolated functional tests |
| `DATA/etc/ansible/playbooks/remove.yml` | Explicitly deregister selected instances |
| `.github/workflows/runner-smoke.yml` | Smoke workflow with a required `runner_group` dispatch input |
| `Taskfile.yml` | Local setup, inventory/Vault helpers, targeted playbooks and validation |
| `scripts/setup.py` | Interactive local configuration and orchestration of existing tasks |

Tool setup lives in `DATA/etc/ansible/roles/tools/tasks/`: `docker.yml`,
`compose.yml`, `virtualization.yml`, `vagrant.yml`, `kubectl.yml`, `minikube.yml`,
`helm.yml` and `wasmtime.yml`. `main.yml` runs shared validation and preparation,
then enabled tools in dependency order. Docker and Compose share one validated
package transaction; `compose.yml` checks the installed plugin. Shared artifact
and package helpers retain checksum verification and guarded upgrades.
`minikube-initialize.yml` handles explicitly requested cluster creation after
all tool installation, separately from installing the Minikube binary.
These task files are internal to the role; use `provision.yml` so preflight,
account preparation and dependency checks always run.

Run Task commands from the repository root. Paths below are relative to it.
Inventory and remote tasks load `DATA/etc/ansible/ansible.cfg`; local validation
uses the tracked `DATA/etc/ansible/templates/ansible.cfg`, independently of
operator configuration and secrets.
For direct Ansible commands, select the local configuration first:

```console
export ANSIBLE_CONFIG="$PWD/DATA/etc/ansible/ansible.cfg"
```

## Version and installation policy

All versions are variables. The complete non-secret example configuration is
`DATA/etc/ansible/templates/group_vars/all.yml`; instance fields are illustrated in
`host_vars`. Role defaults document additional overrides.

| Component | Initial version | Source/integrity |
|---|---|---|
| Actions runner | `2.338.0` | Official `actions/runner` release; asset SHA256 or supplied reviewed SHA256 |
| Docker Engine | `29.1.3` | Ubuntu apt if exact version available; otherwise signed Docker apt repository |
| Compose v2 plugin | `2.40.3` | Same explicit apt-source choice; independently resolved exact plugin version |
| kubectl | `1.37.1` | `dl.k8s.io`, official versioned SHA256 |
| Minikube | `1.39.0` | Official `kubernetes/minikube` release and SHA256 |
| Kubernetes in Minikube | `1.37.0` | Explicit Minikube start version; only downloaded on optional initialization |
| Helm | `4.3.0` | `get.helm.sh`, versioned archive and checksum |
| Vagrant | `2.4.9` | HashiCorp versioned release/checksum |
| vagrant-libvirt | `0.12.2` | Exact RubyGems plugin version, installed separately per runner |
| QEMU/KVM, libvirt | Ubuntu-managed | Supported release's configured Ubuntu repositories |
| Wasmtime | `50.0.0` | Bytecode Alliance x86-64 GNU/Linux release with published asset SHA256 |

`docker_package_source` explicitly selects `upstream` or `ubuntu`.
The default is **ubuntu on both releases**, using each suite's own security and
backport packages, not identical Debian revision strings.
There is **no automatic source fallback**. Noble and resolute have separate
package maps and use their own repository suites:

| Release | Ubuntu choice | Upstream choice |
|---|---|---|
| 24.04 noble | Engine `29.1.3-0ubuntu3~24.04.2`, Compose `2.40.3+ds1-0ubuntu1~24.04.1` | `download.docker.com/linux/ubuntu`, suite noble |
| 26.04 resolute | Engine `29.1.3-0ubuntu4.1`, Compose `2.40.3+ds1-0ubuntu1` | Same official server, **suite resolute**, baseline absent |

On each target, apt metadata is checked for the exact engine, CLI and Compose
versions and dependency resolution is simulated before installation.
Ubuntu's package versions need not equal Docker's upstream release numbers.
The example's `docker_apt_version_overrides` pins the known full package
revisions separately for each release. Role defaults without these overrides
select the highest available packaging revision of the configured upstream
version. Review and update full revision pins when adopting Ubuntu security
updates; missing pinned revisions fail rather than being replaced.
The source map intentionally does not reuse noble packages on resolute.
Verify both suites independently; an unavailable resolute repository is not
permission to install noble packages. The selected Docker key fingerprint is
pinned in role defaults.

Publication checks on 2026-10-27 found the exact baseline packages in
[Docker's noble pool](https://download.docker.com/linux/ubuntu/dists/noble/pool/stable/amd64/),
but not in its
[resolute pool](https://download.docker.com/linux/ubuntu/dists/resolute/pool/stable/amd64/)
(whose engine/plugin versions start at 29.3.1/5.0.2 respectively).
Ubuntu's native Resolute packages **do** meet the baseline:
`docker.io=29.1.3-0ubuntu4.1` (security update; base `29.1.3-0ubuntu4`) and
`docker-compose-v2=2.40.3+ds1-0ubuntu1`.
See Canonical's
[Docker changelog](https://github.com/canonical/docker.io-app/blob/ubuntu/resolute/debian/changelog),
[Compose changelog](https://github.com/canonical/docker-compose-v2/blob/ubuntu/resolute/debian/changelog),
and actual Ubuntu archive
[Docker](https://archive.ubuntu.com/ubuntu/pool/universe/d/docker.io-app/) /
[Compose](https://archive.ubuntu.com/ubuntu/pool/universe/d/docker-compose-v2/)
package listings. Resolute needs its native `universe` and security repositories.
Noble's native security backports also meet the baseline; see its
[Docker changelog](https://github.com/canonical/docker.io-app/blob/ubuntu/noble/debian/changelog)
and [Compose changelog](https://github.com/canonical/docker-compose-v2/blob/ubuntu/noble/debian/changelog).
Enable native Noble `universe`, updates and security repositories as well.
Ubuntu-patched builds are not byte-identical to Docker CE packages.
Canonical's Compose build embeds the full Debian package version in
`docker compose version --short` (including `+ds1-0ubuntu...`); that suffix is
packaging metadata, not permission to accept a different upstream release.
Docker's CLI uses upstream `29.1.3` with the Ubuntu revision in its build field.
These publication checks do **not** establish dependency compatibility; the
per-host apt simulation and real installation remain required.
Other requested releases have official publication evidence:
[runner](https://github.com/actions/runner/releases/tag/v2.338.0),
[kubectl checksum](https://dl.k8s.io/release/v1.37.1/bin/linux/amd64/kubectl.sha256),
[Minikube](https://github.com/kubernetes/minikube/releases/tag/v1.39.0),
[Helm](https://github.com/helm/helm/releases/tag/v4.3.0),
[Vagrant](https://releases.hashicorp.com/vagrant/2.4.9/), and
[vagrant-libvirt](https://rubygems.org/api/v2/rubygems/vagrant-libvirt/versions/0.12.2.json).
Helm archive/checksum delivery and execution passed on both fresh guests on
2026-10-28, following an earlier controller DNS failure.
The [Wasmtime 50.0.0 asset listing](https://github.com/bytecodealliance/wasmtime/releases/expanded_assets/v50.0.0)
publishes SHA256
`77c19ee0437991f9ac7837b9c269d9c7076744f85dad263fea5214cc2723c7ff`
for `wasmtime-v50.0.0-x86_64-linux.tar.xz`. The GNU/Linux build is the intended
x86-64 artifact; installation and WASI execution passed on both fresh guests.

`tools_artifact_sha256` can pin reviewed archive digests. A required missing
digest must be populated from an official release/checksum publication, not
from an untrusted mirror or by hashing a download without an independent source.
Changing versions requires reviewing the matching digests too. No mutable
installation scripts are executed. Apt-managed QEMU/libvirt and transitive
package/plugin dependencies are **not a fully frozen repository snapshot**;
use an approved apt snapshot and artifact mirror for stronger reproducibility.
The libvirt plugin's root gem is checksum-pinned and installed as each runner
user; its transitive dependencies resolve from RubyGems by default. For offline
or fully locked plugin deployment, configure `vagrant_libvirt_gems` with the
complete reviewed `{name, version, sha256}` dependency closure. That optional
lock must match Vagrant's bundled Ruby; guessed dependency sets are not shipped.

## Runner accounts and host capacity

The templates configure **one runner per host**, using the dedicated Linux user
`ghrunner`. Set `runner_instances[].user` to choose a different account before
provisioning. Existing local inventory files are preserved by
`task inventory:init`; update their user setting explicitly for a fresh target.
Existing deployed accounts are not renamed or adopted automatically.

One runner per host or VM is recommended for this setup: it normally executes
one job at a time and avoids concurrent jobs competing for shared runtime
resources. Persistent containers, VMs, clusters and files can still outlive a
job, so workflows must clean up their own resources.

Multiple runners per host are supported with no fixed count imposed by this
project. Every instance needs a unique runner name, Linux user, installation
and work directories, and effective Minikube profile. Capacity depends on the
combined job workload, not just the runner process. Jobs share the Docker
daemon, system libvirt, host ports, CPU, memory and disk; separate users do not
make those runtimes isolated. Use multiple runners on one host only for trusted
workloads with coordinated resource naming, limits and cleanup. For concurrent
jobs with stronger isolation, use one runner per dedicated VM and size the
underlying server for their combined workload.

## Inventory, secrets and authentication

1. Run `task inventory:init` to populate `DATA/etc/ansible` (gitignored).
   The template `hosts.yml` becomes `hosts`; existing files are preserved.
2. Replace hostnames and `ansible_user`. Keep SSH host-key checking enabled.
3. Configure shared versions/switches in `group_vars/all.yml`, and a distinct
   `runner_instances` list in each host's `host_vars/<inventory_hostname>.yml`.
   Names must be unique **across the organization**, not just within a host.
4. Create encrypted secrets, for example:

   ```console
   task vault:create
   ```

   Put `github_api_token` **or** `runner_registration_token` in the encrypted
   file. Do not put secret values in command-line `-e`, shell history, Git,
   plaintext inventory, CI logs, or generated version reports. Vault passwords
   should come from a prompt or your external secret manager.

For unattended fresh tokens, use a short-lived **GitHub App installation access
token** installed in the target organization, with organization
**Self-hosted runners: read and write** permission. A fine-grained PAT with the
same organization permission is another option; apply your organization's
approval/expiry policies. Mint App JWTs/installation tokens outside this project
using your secret broker, and inject only the installation token as
`github_api_token`. This avoids persisting an App private key on targets.
The broker signs an App JWT and calls
`POST /app/installations/{installation_id}/access_tokens`; refresh that
installation token before each unattended provisioning window. For
environment-based injection, a production group variable can contain the
non-secret expression
`github_api_token: "{{ lookup('ansible.builtin.env', 'GITHUB_API_TOKEN') }}"`.
Have the broker populate that environment variable without echoing it; do not
put its value in the Ansible command line.
Classic PATs require broader `admin:org` access and are not the preferred
minimum-permission method.

The role requests fresh organization registration/removal tokens from GitHub
when needed. Registration tokens normally expire after one hour. A supplied
`runner_registration_token` avoids API authentication, but cannot prove remote
availability or busy status and may need refreshing between hosts.
API requests and credential-bearing configuration/removal tasks use `no_log`.
Tokens are not stored in manifests or service units and are not passed in
registration command arguments. GitHub's runner necessarily retains its own
registration credentials inside its restricted installation directory.
Treat that directory, Ansible's process memory, and the runner account as
sensitive; do not use verbose debugging or export full hostvars.

Create your selected runner group in GitHub first, select the approved private repositories,
and leave **Allow public repositories** disabled. This
project does not create groups or broaden group policy. No `--replace` is used:
a name collision fails instead of replacing another runner.

Each instance has a dedicated non-root account, installation, work directory
and `mare-runner-<name>.service`. Adding another host means another inventory
entry and globally unique names; adding an instance means another list entry,
not copying an existing installation. Existing unmanaged installations/accounts
are treated as conflicts rather than silently adopted.

## Provision, verify and repeat

Review the inventory and use a disposable supported host first:

```console
task check LIMIT=noble_runner
task provision LIMIT=noble_runner
task verify LIMIT=noble_runner
# Repeat exactly, retain the recap as the idempotence acceptance evidence:
task provision LIMIT=noble_runner
```

Repeat independently for `resolute_runner`. A second converged provisioning run
must have no unnecessary changes. Read-only probes use `changed_when: false`;
stable configuration files and ownership records are compared before writes.
Full provisioning and zero-change repeats were demonstrated on both supported
releases; see the retained acceptance evidence below.

Check mode validates facts and existing state where practical. On a fresh
host, package metadata, downloaded binaries, new accounts, registration,
systemd and runtime checks cannot all be predicted: do not treat a successful
dry run as acceptance. No functional tests should be run in check mode.
Tags include `preflight`, `tools`, `runner`, `verification`, and component tags
within the roles. Preflight runs even for tagged provisioning.

Feature switches: `docker_enabled`, `docker_compose_enabled`, `kubectl_enabled`, `minikube_enabled`,
`helm_enabled`, `virtualization_enabled`, `vagrant_enabled`,
`vagrant_libvirt_enabled`, `wasmtime_enabled`. `kubernetes_enabled` supplies
the default for its three individual tools; disable individual tools as needed.
Disabled features are not uninstalled, nor is their existing state removed.
Dependencies still apply: Docker-driver initialization needs Docker, and
vagrant-libvirt needs Vagrant and libvirt.

`verify.yml` distinguishes executable/version checks, service health, account
access and optional GitHub registration/online checks. API checks require
`github_api_token`; a registration token alone cannot authorize them.
The secret-free host software inventory is `/var/lib/mare-runner/versions.json`.

## Tool access and Minikube lifecycle

Service units explicitly set `PATH`, `HOME` and `TMPDIR`, so login shell
configuration is not required. Each runner uses its own owner-only
`<work_dir>/.tmp` directory, avoiding temporary-file ownership conflicts after
an account migration. Verification runs tools as each runner account.
Docker and libvirt/KVM group memberships are applied to the service; an
already-running service needs guarded maintenance to acquire changed groups.

Provisioning explicitly denies SSH login for each runner account through a
validated, root-owned OpenSSH drop-in; operator SSH access is preserved. The
denial remains when an account is retained or purged, so recreating that service
identity cannot accidentally restore remote login. Hosts without OpenSSH skip
this configuration.

The service prevents privilege gains through setuid binaries/file capabilities,
drops its Linux capability set, makes system configuration read-only, hides other
users' home directories and processes, and protects kernel settings, modules,
logs and cgroups. Only the runner's own home, installation and work directories
are exposed beneath protected home directories. `task verify` checks the policy
and the running process. Changing an existing unit requires guarded maintenance.
KVM device access, shared temporary paths needed by Docker bind mounts, and
executable memory needed by Wasmtime JIT remain available. Use the private
`TMPDIR` for temporary files.

Runner services prepend the root-owned `/usr/local/libexec/mare-runner` directory
to their configured PATH. Its `tar` link selects Ubuntu's `bsdtar`
(`libarchive-tools`) for action downloads and job tools; the host's `/usr/bin/tar`
and operator PATH are unchanged. This preserves `RestrictSUIDSGID=yes`:
systemd deliberately blocks `openat2` under that restriction, while Ubuntu
26.04's GNU tar requires it for nested archive extraction. See the
[systemd compatibility documentation](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html#RestrictSUIDSGID=).
Do not remove the restriction or replace the host tar binary to work around
bootstrap failures. Helper installation uses the same guarded package flow,
so dependency updates still require explicit maintenance and drain approval.

The smoke workflow includes a pinned `actions/checkout`, then downloads and
SHA256-verifies its pinned archive independently and extracts it into a fresh
test-owned directory under the actual job confinement. It checks retained
capability, privilege, mount, process/home visibility, SSH and set-ID denial
controls, and removes only its own extraction directory. This cold extraction
is required even when GitHub has already cached the action.

**Docker daemon access is effectively host-root access.** Shared Docker,
libvirt and KVM access do not provide isolation against hostile jobs. Do not
run untrusted pull requests or mutually untrusted tenants on these hosts.
Use separate hosts/VMs and restricted runner groups for trust boundaries.
Multiple runner accounts do not isolate a shared Docker daemon, system
libvirt connection, networks or storage. Jobs must use unique names and
resource limits; never use blanket prune/delete operations.

Docker's existing images, containers, volumes, networks and daemon configuration
are preserved. This project does not write `daemon.json`; apply any desired
daemon changes through a separate reviewed maintenance change, merging existing
keys or rejecting conflicting settings rather than replacing the file.

`task setup:runner` defaults to initializing Minikube when its tools are enabled.
For manual provisioning, set `minikube_initialize: true` after capacity review.
Rerun provisioning with that explicit switch to initialize the owned profiles.
The same playbook handles installation and optional initialization; matching
installed tools remain unchanged.

```console
task provision LIMIT=noble_runner -- -e '{"minikube_initialize":true}'
# Read-only status on the example single-instance target:
sudo -u ghrunner env HOME=/home/ghrunner \
  KUBECONFIG=/home/ghrunner/.config/runner-kubernetes/minikube/config minikube --profile minikube status
```

Defaults: Docker driver, profile `minikube`, Kubernetes `1.37.0`, 2 CPUs,
16000 MB RAM. Multiple instances use separate profile identities. Each account
uses a separate managed kubeconfig, not the existing default Kubernetes
configuration. Unowned profiles are rejected; existing contexts are not
adopted. Provisioning never implicitly stops or deletes a profile.
Stop/start/delete clusters only as the owning account with the explicit
profile and managed kubeconfig, after draining every dependent runner.
Effective profile names must be unique across runner instances on the host.
Docker initialization checks the shared local daemon (including stopped
containers, networks and volumes) before reserving a profile and again before
startup. Exact resource identities are retained in a root-owned `0600`
`<profile>.json.docker.json` record beside the profile marker. Same-name resources
without that record, or replaced resources, are rejected even when Minikube
labels match. Existing clusters created before this guard are not adopted.
If startup is interrupted before the resource record is saved, preserve the
resources and investigate privately or choose a fresh profile; rerunning does
not authorize their adoption. Serialize initialization and other Docker changes
on each host; these checks do not lock out external Docker administrators.
Minikube uses the local `/var/run/docker.sock`, independent of user Docker
contexts.

Separate profiles still contend for the same host's CPU, memory, disk, ports
and Docker daemon.

Libvirt uses `qemu:///system`; runner accounts receive only the required
`libvirt` and `kvm` groups. Verification opens `/dev/kvm` and queries the stable
KVM API as the runner account, then checks the system connection. `libvirtd.socket`
is enabled at boot; the daemon may exit when idle and start again on demand.
Ubuntu 24.04 installs `qemu-kvm`; Ubuntu 26.04 selects the concrete
`qemu-system-x86` provider because `qemu-kvm` is virtual there. Both explicitly
install `qemu-utils` and `dnsmasq-base` for image and NAT support when apt
recommendations are disabled. Existing domains, networks, pools and disks are
untouched.
Allocate VM CPU/memory/storage for aggregate concurrent jobs and avoid sharing
domain names. The project does not create a default libvirt network or storage
pool: provide an approved network/pool before running VM tests.

Wasmtime supports core WebAssembly and WASI Preview 1 command modules (the
included small test), plus Preview 2/component execution as supported by the
pinned release. WASI HTTP needs a compatible WASI HTTP component and explicit
`wasmtime serve` configuration/network permissions; a core Preview 1 command is
not an HTTP service. No Rust SDK, Emscripten, WasmEdge or unrelated toolchain is
installed. Grant filesystem/network capabilities only as required by a workload.

## Functional acceptance and workflow routing

Use **disposable, idle, authorized hosts**. Set both
`functional_tests_enabled: true` and `functional_tests_confirmed: true`.
Supply an immutable container image digest and an explicitly pinned Vagrant box
URL/checksum in `functional_container_image` and
`functional_vagrant_box_{name,version,url,sha256}`.
`functional_vagrant_storage_pool` selects an approved existing libvirt pool
(default `default`). Tests create
unique scopes and use cleanup blocks; cleanup failures are failures, not
ignored successes. Never run these tests against unrelated kubeconfigs.

The suite covers a Docker container; Compose application up/down; isolated
Minikube namespace/workload create/delete; a small local Helm chart
install/uninstall; libvirt Vagrant VM boot/destroy; and a small WASI program.
Kubernetes tests require prior explicit Minikube initialization.
Tests only run for enabled tools; a skipped test is not a verified capability.
Do not use a mutable container tag, an unversioned Vagrant box, or an arbitrary
download URL as acceptance evidence.

Run the manual `runner-smoke.yml` workflow **only after operator approval**.
Supply the workflow's required `runner_group` input explicitly; it has no default.
For a repository workflow, use your configured group plus a dedicated `mare-smoke`
label. This example uses a group named `Platform CI`:

```yaml
jobs:
  build:
    runs-on:
      group: Platform CI
      labels: [self-hosted, linux, x64, mare-smoke]
    steps:
      - run: docker version && wasmtime --version
```

Use a unique acceptance label or instance-specific label to ensure routing to
the newly provisioned runner, not an existing production runner. GitHub's
default labels are retained. The workflow is supplied, **not dispatched** by
provisioning or development.

GitHub requires a `workflow_dispatch` workflow to exist on the default branch
before its first manual dispatch; selecting the PR branch alone does not
bootstrap it. See [GitHub's manual workflow requirements](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).
Keep your selected group restricted to private repositories. Run routed acceptance from an
approved private repository, using a reviewed copy of this smoke workflow on
that repository's default branch and unique test-runner labels. This public
repository can use GitHub-hosted runners for its own CI. Preserve the selected group's private
repository policy; do not enable public access for acceptance.

## Safe maintenance, upgrades and removal

1. Stop **new** jobs by removing repository access to the runner group or
   changing workflow routing to a drained group. Coordinate this in GitHub;
   merely stopping a service is not a drain.
2. Wait for all jobs on **every affected host instance** to finish. With an API
   token, busy status is checked where possible; without it, operator
   confirmation is mandatory. Busy status has an unavoidable race unless new
   job assignment has already been disabled.
3. Set `runner_maintenance_confirmed: true` for runner maintenance. Tool/package
   maintenance has separate explicit authorization documented in its defaults.
   Never authorize these globally in a routine production inventory.
4. Update version variables and matching checksums, review release notes, and
   explicitly allow tool upgrades with `tool_allow_upgrades: true`.
   Re-registration due to changed labels/group/work/update policy requires
   `runner_allow_reconfigure: true`.
5. Run provisioning and verification on one drained host at a time; restore
   routing only after verification, then reset maintenance switches.

Runner automatic updates are **disabled by default** for reproducibility.
GitHub requires updates within 30 days of a release and can enforce critical
security updates sooner: operators must schedule guarded upgrades promptly.
With `runner_disable_update: false`, `runner_version` is an installation floor,
not a recurring downgrade target; a newer auto-updated installation is retained.
The runner's own update mechanism remains responsible for GitHub-required
updates. Do not pin an obsolete runner indefinitely.

Reboot-required status is reported. Reboots require `allow_reboot: true` and
`maintenance_confirmed: true`; only use those after the drain procedure.
Development never sets either switch or reboots a host.

For removal, narrow `runner_instances` to the intended entries in a separate
inventory/override and inspect `--list-hosts` before executing:

```console
ansible-playbook -i DATA/etc/ansible/hosts DATA/etc/ansible/playbooks/remove.yml --list-hosts
ansible-playbook -i DATA/etc/ansible/hosts DATA/etc/ansible/playbooks/remove.yml \
  --extra-vars @DATA/etc/ansible/vault/vault.yml --vault-password-file DATA/etc/ansible/vault/password \
  --limit noble_runner -e '{"runner_allow_removal":true,"runner_maintenance_confirmed":true}'
```

Supply a fresh `runner_removal_token` through Vault or allow the API to mint one.
Ordinary provisioning never invokes removal. Preserve workload state and review
any retained account/work files separately; do not recursively delete shared
directories or copy credentials to another host.
Removal preserves local installation/work/home data and accounts by default.
`runner_purge_data: true` is a separate, destructive opt-in for the selected
managed instance; review those paths and back up needed state first.

## Troubleshooting

* **Missing versions/checksums:** inspect the publisher's exact release, apt
  suite and available versions. Correct the explicit configuration only after
  review. Never bypass checksum validation or point resolute at noble.
* **Docker permission denied:** inspect account supplementary groups and the
  service's running groups. Drain, then restart under explicit maintenance
  authorization. Check `systemctl status docker`; do not chmod the socket.
* **KVM unavailable:** inspect firmware, `vmx`/`svm`, `/dev/kvm`, `kvm` membership
  and hypervisor nested-virtualization settings. Enable outer-host nesting or
  select a suitable host, not world-writable device permissions.
* **libvirt denied:** check `libvirtd`, group membership and
  `virsh -c qemu:///system list --all` as the runner. Do not change to an
  unrelated session connection or grant broad sudo.
* **Minikube errors:** check owning user, explicit profile/kubeconfig, available
  memory/CPUs, Docker access and requested Kubernetes availability. Do not
  delete an existing profile as a troubleshooting shortcut.
* **Works interactively, not as service:** inspect the unit's PATH/HOME and use
  verification as the service account; avoid dependencies on `.bashrc`.
* **Registration errors:** check organization/group membership and policy,
  App installation permissions, token expiry, name uniqueness and outbound
  HTTPS. Do not print a token, runner credential file, or full Ansible hostvars.
* **Maintenance blocked:** drain in GitHub, wait until idle, and supply explicit
  authorization. Do not bypass busy checks to force an upgrade.

## Acceptance evidence to retain

For **each** release, retain sanitized Ansible recaps for first and second
provisioning, software inventory, service/account checks, API availability,
runtime/cleanup results, and the smoke workflow URL. Record actual host
virtualization type and KVM test result. Do not retain tokens, machine IDs,
runner credential files, caches, kubeconfigs or workload data in reports.
Local syntax checks alone are not platform acceptance; absent infrastructure
and credentials remain external acceptance prerequisites.

Run `task validate` (an alias for `task syntax`) to syntax-check all three
playbooks using the tracked configuration and example inventory, without
contacting runner hosts.

Keep sanitized operational reports locally under `tests/evidence/` (ignored by
Git), or in a private artifact store. These generated reports are not repository
source and should not be committed.

Reports retain actual versions, recaps and source/log hashes. Registration used
a short-lived token; GitHub API availability checks were skipped and the signed-in
UI confirmed both runners Idle in ENG. Local smoke execution does not prove
GitHub job routing. PR #1 merged with dispatched smoke retained as a post-merge
gate, to be completed from an approved private repository. ENG remains restricted
to private repositories.
