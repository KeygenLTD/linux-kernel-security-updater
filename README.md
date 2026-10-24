# Linux Kernel Security Updater (LKSU)

![LKSU kernel update, verification and fallback illustration](docs/assets/lksu-hero.png)

> **Status: v0.3 early preview.** Unit tested, but not yet integration tested across AlmaLinux 8/9/10, BIOS/UEFI, DNF and GRUB combinations. Do not activate automatic installation or reboot on production hosts until those checks and a provider-console recovery drill pass.

Early production-oriented release for **AlmaLinux 8, 9 and 10**. LKSU uses the distribution's enabled DNF repositories. It does not enable testing repositories, select a CVE-specific build, download arbitrary RPMs, or reboot a machine automatically.

## Safety model

- Default policy is `check-only`. The scheduled timer checks daily and emails a report.
- `security-only` reads DNF security updateinfo and reports advisory IDs, severity, affected kernel packages and CVEs. `all-stable` permits all kernel updates from enabled repositories.
- Before installation LKSU checks AlmaLinux version, root privileges, required tools, `/boot` free space, a GRUB configuration, the running kernel's image, and its installed RPM. Its disk threshold is 500 MiB; host-specific layouts may require more.
- Installation overrides DNF's `installonly_limit` to preserve installed kernels. LKSU checks that the running kernel's RPM and boot image still exist, then records the previous kernel. It does **not** create a full boot, VM, filesystem, or data backup.
- Maintenance windows use an explicit local start time and duration. Installation and reboot are separate operations; automatic reboot defaults to disabled.
- A trial reboot keeps the old kernel as the persistent GRUB default and selects the new kernel once with `grub2-reboot`. Successful service and HTTP/HTTPS health checks promote the new kernel.
- Agents can send HMAC-signed reports over HTTPS to the SQLite-backed `lksu-fleet` collector and bearer-token-protected web dashboard.
- Optional Security Watch reports LKSU/config integrity changes, inactive configured security services, non-enforcing SELinux, repeated SSH failures and successful root SSH logins. It never edits files, blocks addresses or removes users.
- The fleet dashboard marks a server silent/stale when its signed heartbeat is older than the configured threshold.
- `lksu select-old` selects the previous kernel as the default for the **next** boot and verifies GRUB's selection. It does not cause a reboot or guarantee recovery from an unbootable machine. A failed boot may require a provider console and manual GRUB selection. Keep a current provider snapshot and console access.
- A pending update blocks a second install until successful post-boot verification. Failed verification leaves the pending state and requires investigation.

## Install on a test VM first

The recommended path is the one-command installer below. Manual installation is available for operators who want to inspect each step. LKSU supports Postmark, SMTP2GO, custom SMTP, local mail, or no email.

```bash
sudo dnf install -y python3 python3-pip grubby
sudo python3 -m pip install --prefix=/usr/local .
sudo lksu configure
sudo lksu check
sudo install -m 644 systemd/lksu.service systemd/lksu.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lksu.timer
systemctl list-timers lksu.timer
```

## One-command setup (recommended)

For a pinned release on AlmaLinux 8/9/10:

```bash
curl -fsSL https://raw.githubusercontent.com/KeygenLTD/linux-kernel-security-updater/v0.3.9/bootstrap.sh | sudo bash
```

This installs LKSU, asks for the report email and provider settings, then runs a read-only check and sends the first report. It does not enable automatic updates or reboot unless explicitly selected.

## Manual operations

```bash
sudo /usr/local/bin/lksu configure
sudo /usr/local/bin/lksu check
sudo /usr/local/bin/lksu scheduled
sudo /usr/local/bin/lksu apply
sudo /usr/local/bin/lksu maintenance
sudo /usr/local/bin/lksu stage-reboot
sudo /usr/local/bin/lksu verify
sudo /usr/local/bin/lksu select-old
sudo /usr/local/bin/lksu security-baseline
sudo /usr/local/bin/lksu security-check
```

`check` and `scheduled` are read-only. `apply` installs the configured kernel policy. `stage-reboot` prepares a one-shot trial boot; it does not guarantee recovery from an unbootable host. `verify` checks the running kernel and configured health checks. `select-old` selects the preserved previous kernel for the next boot.

To enable alert-only Security Watch, first review `security_watch` in the root-only configuration, create a trusted baseline, then enable its timer:

```bash
sudo lksu security-baseline
sudo lksu security-check
sudo systemctl enable --now lksu-security-watch.timer
```

Re-run `security-baseline` only after verifying that an intentional LKSU or watched-file change is trusted. Security Watch does not attempt malware removal or general system rollback; use auditd, AIDE, Wazuh, CrowdSec or another dedicated security platform where appropriate.

The interactive setup requests a report address, SMTP host/port, username, password or app password, policy, and health-check service names. Configuration is written to `/etc/lksu/config.json` as mode 0600. Use a dedicated SMTP credential. Port 465 uses implicit TLS; other ports require STARTTLS and certificate verification. Avoid shared administrator account credentials. Test mail delivery with `sudo lksu scheduled` before relying on alerts.

To use automatic installation, change `policy` from `check-only` to `all-stable` in `/etc/lksu/config.json` while retaining owner root and mode 0600. This opt-in runs `dnf upgrade` for the five kernel packages only. Review `dnf repoquery --upgrades kernel kernel-core kernel-modules kernel-modules-core kernel-modules-extra` first. LKSU will **never** automatically reboot. The timer may run outside your maintenance window, so leave policy as `check-only` unless installation at any timer run is acceptable.

## Manual operating procedure

```bash
sudo lksu check
sudo lksu apply                 # requires security-only or all-stable policy
sudo cat /var/lib/lksu/state.json
sudo lksu stage-reboot          # preserves old default, stages new kernel once
# Confirm provider snapshot and console access, then reboot in an approved window.
sudo reboot
sudo lksu verify
uname -r
systemctl is-active lsws mariadb lscpd
```

If the new kernel boots but health checks fail, investigate the services first. To select the saved previous kernel for a later manual reboot:

```bash
sudo lksu select-old
grubby --default-kernel
# Reboot only after assessing the problem and confirming console access.
```

If the new kernel does not boot at all, use the provider console to select the old GRUB entry. LKSU cannot run on an unbootable host.

## Verification and release limits

Run local tests with `python3 -m pip install -e .` and `python3 -m unittest discover -s tests -v`. The tests use temporary files and mocks; they do not prove real AlmaLinux DNF metadata, GRUB one-shot behavior, reboot recovery, RPM installation, SMTP delivery, HTTP services or fleet TLS. Before production use, perform AlmaLinux 8/9/10 BIOS and UEFI VM integration runs and a real console recovery drill. The previous kernel is not a complete backup.

`install.sh` installs the application without enabling timers or automatic actions. `packaging/lksu.spec` is an RPM packaging preview; a signed RPM still requires a real AlmaLinux build and signing pipeline. Example agent and collector configurations are provided in `config.example.json` and `fleet-server.example.json`.

When `automatic_reboot` is explicitly set to `true`, `lksu maintenance` stages the one-shot trial and requests a reboot only after a successful installation inside the configured window. The default remains `false`.

For `vmi942177`, the reported running kernel is `6.12.0-211.51.1.el10_2` and the previously observed repository candidate was `6.12.0-211.68.1.el10_2`. These are historical conversation values. Run `lksu check` on the actual host to establish current state before deciding on any update.
