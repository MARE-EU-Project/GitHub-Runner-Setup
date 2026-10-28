# GitHub Actions runner hosts

Reusable Ansible provisioning for persistent **organization-level** runners in
[`MARE-EU-Project`](https://github.com/MARE-EU-Project), runner group **ENG**.
Both are configurable. Only Ubuntu **24.04 (noble)** and **26.04 (resolute)**,
**x86-64**, are accepted. This project is not a VM image: never clone a
registered runner, its credentials, machine identity, caches, or kubeconfig.

## Safety and validation status

**Full runner provisioning and registration passed; dispatched workflow routing remains pending.**
On 2026-10-28, fresh disposable Ubuntu 24.04 and 26.04 KVM guests passed
preflight and tool installation, repeat runs with `changed=0`, and functional
Docker, Compose, Kubernetes, Helm, Vagrant/libvirt VM boot/guest-command and
Wasmtime/WASI tests. Runs resumed after the acceptance fixes documented below;
the runner role and registration were not invoked. Both disposable guests and
their test resources were removed after collecting evidence.

The 2026-10-27 tests on an existing Ubuntu 26.04.1 runner host separately covered
private directory ownership, nested work paths, Docker resource ownership and
fresh/repeat isolated Minikube initialization. The existing production runner,
its Docker containers and Minikube cluster remained running and unchanged.
KVM acceptance requires physical hosts or VMs exposing nested virtualization,
not containers. A separate pair of fresh guests subsequently passed full
`provision.yml`, registration with an operator-supplied short-lived token,
repeat provisioning with `changed=0`, and corrected `verify.yml` checks.
Both runners appeared Idle in ENG. The exact smoke script, including WASI,
also passed locally as each runner account; this does not prove job routing.
The test registrations and VMs were removed with operator approval.
Dispatched acceptance remains blocked by the workflow bootstrap and existing
runner-group repository policy described below.

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
  2.21.5). `requirements.yml` declares no external collections; only
  `ansible.builtin` modules are used. Pin controller packages in your controller
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
| `roles/preflight` | Read-only platform, identity, virtualization and reboot checks |
| `roles/tools` | Release-aware packages, verified binaries, account permissions, optional Minikube |
| `roles/runner` | Owned installations, GitHub registration, systemd, guarded maintenance/removal |
| `roles/verification` | Versions, services, account access, inventory and opt-in runtime tests |
| `inventory/example` | Two release groups, shared `group_vars`, per-host instances |
| `playbooks/provision.yml` | Install/configure, without functional workloads |
| `playbooks/verify.yml` | Verify, optionally run isolated functional tests |
| `playbooks/minikube.yml` | Explicit post-installation Minikube initialization |
| `playbooks/remove.yml` | Explicitly deregister selected instances |
| `.github/workflows/runner-smoke.yml` | Manually dispatched runner-routing acceptance workflow |

Use the repository root as the working directory for `ansible.cfg`.
Paths below are relative to that root.

## Version and installation policy

All versions are variables. The complete non-secret example configuration is
`inventory/example/group_vars/all.yml`; instance fields are illustrated in
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

## Inventory, secrets and authentication

1. Copy `inventory/example` to `inventory/production` (gitignored).
2. Replace hostnames and `ansible_user`. Keep SSH host-key checking enabled.
3. Configure shared versions/switches in `group_vars/all.yml`, and a distinct
   `runner_instances` list in each host's `host_vars/<inventory_hostname>.yml`.
   Names must be unique **across the organization**, not just within a host.
4. Create encrypted secrets, for example:

   ```console
   ansible-vault create inventory/production/group_vars/github_runners/vault.yml
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

Create group ENG in GitHub first and restrict its repository access. This
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
ansible-galaxy collection install -r requirements.yml
ansible-playbook -i inventory/production/hosts.yml playbooks/provision.yml --ask-vault-pass --check
ansible-playbook -i inventory/production/hosts.yml playbooks/provision.yml --ask-vault-pass --limit noble_runner
ansible-playbook -i inventory/production/hosts.yml playbooks/verify.yml --ask-vault-pass --limit noble_runner
# Repeat exactly, retain the recap as the idempotence acceptance evidence:
ansible-playbook -i inventory/production/hosts.yml playbooks/provision.yml --ask-vault-pass --limit noble_runner
```

Repeat independently for `resolute_runner`. A second converged provisioning run
must have no unnecessary changes. Read-only probes use `changed_when: false`;
stable configuration files and ownership records are compared before writes.
This behavior is implemented but has **not** been demonstrated on remote hosts
in this development environment.

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

Service units explicitly set `PATH` and `HOME`, so login shell configuration
is not required. Verification runs tools as each runner account.
Docker and libvirt/KVM group memberships are applied to the service; an
already-running service needs guarded maintenance to acquire changed groups.

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

Set `minikube_initialize: true` only after installation and capacity review.
Use `playbooks/minikube.yml` to initialize after provisioning without reinstalling
host tools; it requires that explicit switch and the Docker driver.

```console
ansible-playbook -i inventory/production/hosts.yml playbooks/minikube.yml \
  --limit noble_runner -e '{"minikube_initialize":true}'
# Read-only status on the example single-instance target:
sudo -u gha-build env HOME=/home/gha-build \
  KUBECONFIG=/home/gha-build/.config/runner-kubernetes/minikube/config minikube --profile minikube status
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
The default routing is group ENG plus a dedicated `mare-smoke` label:

```yaml
jobs:
  build:
    runs-on:
      group: ENG
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
The selected runner group must also permit the repository and its visibility.
Do not broaden an existing production group's public-repository access just to
complete acceptance; use an explicitly approved group and bootstrap procedure.

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
ansible-playbook -i inventory/production/hosts.yml playbooks/remove.yml --list-hosts
ansible-playbook -i inventory/production/hosts.yml playbooks/remove.yml --ask-vault-pass \
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

Development validation:

Run `python3 -m unittest discover -s tests -v` for the directory-layout and
Docker ownership and Vagrant cleanup regressions. These tests use temporary
local directories and fixture Docker/virsh responses; they do not initialize a
cluster, access libvirt or register runners.
Run `ansible-playbook playbooks/<name>.yml --syntax-check` for each playbook.
The regressions cover private home/install ancestors, nested work directories,
foreign/stopped containers and replaced daemon resource identities.

| Check | Result |
|---|---|
| Example inventory and playbook YAML | Parsed locally |
| Inventory release groups | Resolved with `ansible-inventory --graph` |
| Example variables and closed safety gates | Passed local Ansible assertions |
| Checksum/version binding | Passed; version overrides do not reuse baseline pins |
| Collection declaration | `ansible-galaxy` succeeds with no external requirements |
| Wasmtime 50.0.0 / vagrant-libvirt 0.12.2 advisory lookup | No known advisories returned |
| Regression suite (13 tests), all four playbook syntax checks | Passed locally (Ansible 2.20.1) and on Ubuntu 26.04.1 (Ansible 2.20.1 and 2.21.5) |
| Real directory tasks, two fresh accounts, home-based/nested layouts, repeat runs | Passed on Ubuntu 26.04.1; isolated accounts/paths removed |
| Docker ownership guard against existing live Minikube resources | Five cases passed; existing Docker resources and runner unchanged |
| Fresh/repeat Minikube initialization, Kubernetes 1.37.0, 2 CPUs / 16000 MB | Passed on Ubuntu 26.04.1; isolated profile/account removed |
| Python pip/venv support | Installed on Ubuntu 26.04.1 through the guarded package role; no upgrades/removals, repeat changed=0, new venv pip works |
| Fresh Ubuntu 24.04 preflight/tools and repeat | Passed after acceptance fixes; tool repeat changed=0; separate full runner run also passed |
| Fresh Ubuntu 26.04 preflight/tools and repeat | Passed after acceptance fixes; tool repeat changed=0; separate full runner run also passed |
| Docker, Compose, Kubernetes and Helm functional tests | Passed on Ubuntu 26.04.1 with a digest-pinned image and isolated profile; scoped cleanup passed |
| KVM/Vagrant VM boot, WASI runtime acceptance | Passed on Ubuntu 26.04.1 with Vagrant 2.4.9, plugin 0.12.2, pinned Debian 12 fixture and Wasmtime 50.0.0; scoped cleanup passed |
| Full runner provisioning, registration and repeat on both fresh releases | Passed using the short-lived registration token; first ok=367/changed=47 each, repeats changed=0 |
| Runner service/account verification and GitHub availability | Passed after fixing the remaining Resolute KVM probe; both runners observed Idle in ENG |
| Exact smoke script with WASI under both runner accounts | Passed locally; no GitHub-dispatched job claimed |
| Dispatched smoke workflow | HTTP 404: workflow absent from default branch; ENG also disallows public repositories while this repository is public; policies unchanged |
| Follow-up regression suite (15 tests), four playbook syntax checks | Passed with ansible-core 2.21.5; cleanup tests preserve unrelated and ambiguous volumes |
| All six runtime tests on both fresh Ubuntu guests | Passed, including nested KVM API 12, Vagrant guest command and WASI stdout; scoped cleanup passed |

The [2026-10-28 sanitized acceptance report](tests/evidence/2026-10-28-remaining-acceptance.json)
records immutable cloud-image pins, actual versions, final recaps, log hashes
and cleanup checks. Fresh-guest runs resumed after correcting Resolute's concrete
QEMU package, explicit `qemu-utils`/`dnsmasq-base` dependencies, libvirt socket
activation and supported `virsh vol-list` parsing.

The subsequent [full registration acceptance report](tests/evidence/2026-10-28-registration.json)
records fresh full provisioning, zero-change repeats, service/account checks,
GitHub UI availability and local smoke results. Initial Resolute verification
exposed a second external `test -r/-w` KVM check in the runner verification role;
the actual open/ioctl probe now verifies access there too. Both final
verification runs passed without relaxing permissions or restarting services.
GitHub API online checks were skipped because only a registration token was
supplied; the signed-in UI provided the independent Idle/group/label checks.
Only actual dispatched workflow routing remains unaccepted. The workflow must
first be bootstrapped on the default branch and the repository must be permitted
by an explicitly approved runner-group policy. ENG's production access settings
were preserved.
