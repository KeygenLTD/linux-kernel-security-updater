# Linux Kernel Security Updater (LKSU)

> **Status: early preview.** Unit tested, but not yet integration tested across AlmaLinux 8/9/10, BIOS/UEFI, DNF and GRUB combinations. Do not activate automatic installation on production hosts until those checks and a provider-console recovery drill pass.

Early production-oriented release for **AlmaLinux 8, 9 and 10**. LKSU uses the distribution's enabled DNF repositories. It does not enable testing repositories, select a CVE-specific build, download arbitrary RPMs, or reboot a machine automatically.

## Safety model

- Default policy is `check-only`. The scheduled timer checks daily and emails a report.
- Optional `all-stable` policy permits scheduled installation of available kernel package updates from already enabled repositories. LKSU does not currently classify advisories reliably enough to offer a `security-only` policy. Confirm enabled repositories and the DNF transaction before selecting `all-stable`.
- Before installation LKSU checks AlmaLinux version, root privileges, required tools, `/boot` free space, a GRUB configuration, the running kernel's image, and its installed RPM. Its disk threshold is 500 MiB; host-specific layouts may require more.
- Installation overrides DNF's `installonly_limit` to preserve installed kernels. LKSU checks that the running kernel's RPM and boot image still exist, then records the previous kernel. It does **not** create a full boot, VM, filesystem, or data backup.
- The administrator controls the reboot in an approved maintenance window. After boot, `lksu verify` compares the running kernel to the saved target and checks configured systemd services. Application and website checks remain the administrator's responsibility.
- `lksu select-old` selects the previous kernel as the default for the **next** boot and verifies GRUB's selection. It does not cause a reboot or guarantee recovery from an unbootable machine. A failed boot may require a provider console and manual GRUB selection. Keep a current provider snapshot and console access.
- A pending update blocks a second install until successful post-boot verification. Failed verification leaves the pending state and requires investigation.

## Install on a test VM first

Requires Python 3.9+, DNF, RPM, grubby, systemd, and a configured SMTP service with TLS. On the host, from this directory:

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

The interactive setup requests a report address, SMTP host/port, username, password or app password, policy, and health-check service names. Configuration is written to `/etc/lksu/config.json` as mode 0600. Use a dedicated SMTP credential. Port 465 uses implicit TLS; other ports require STARTTLS and certificate verification. Avoid shared administrator account credentials. Test mail delivery with `sudo lksu scheduled` before relying on alerts.

To use automatic installation, change `policy` from `check-only` to `all-stable` in `/etc/lksu/config.json` while retaining owner root and mode 0600. This opt-in runs `dnf upgrade` for the five kernel packages only. Review `dnf repoquery --upgrades kernel kernel-core kernel-modules kernel-modules-core kernel-modules-extra` first. LKSU will **never** automatically reboot. The timer may run outside your maintenance window, so leave policy as `check-only` unless installation at any timer run is acceptable.

## Manual operating procedure

```bash
sudo lksu check
sudo lksu apply                 # requires all-stable policy
sudo cat /var/lib/lksu/state.json
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

Run local tests with `python3 -m pip install -e .` and `python3 -m unittest discover -s tests -v`. The tests use temporary files and mocks; they do not prove real AlmaLinux DNF, GRUB, SMTP or recovery behavior. Before production use, perform an AlmaLinux 8/9/10 VM integration run and an actual console recovery drill. Do not treat the previous kernel as a complete backup. This release does not provide a maintenance-window reboot scheduler, automatic rollback, CVE mapping, or full application health checks; those features need host-specific validation before activation.

For `vmi942177`, the reported running kernel is `6.12.0-211.51.1.el10_2` and the previously observed repository candidate was `6.12.0-211.68.1.el10_2`. These are historical conversation values. Run `lksu check` on the actual host to establish current state before deciding on any update.
