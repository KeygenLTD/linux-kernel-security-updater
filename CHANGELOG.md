# Changelog

## v0.3.22 — Cross-distribution read-only kernel inventory

- Implement `lksu kernel-inventory --json` for installed APT linux-image and RPM kernel packages including CloudLinux variants.
- Run read-only inventory on an Ubuntu CI host and add unit tests across Python 3.9/3.11/3.13.
- Kernel installation, one-shot reboot and rollback remain AlmaLinux-only and all unverified backends remain fail-closed.


## v0.3.21 — Actual Linux container image detection tests

- CI validates distribution detection and fail-closed update/reboot gates against Ubuntu 24.04, Debian 12, Rocky 9, Fedora, Alpine and Arch Linux official container images.
- This is **not** a kernel installation/reboot/rollback test. Actual kernel update support remains AlmaLinux 8/9/10 only; CloudLinux requires dedicated LVE/kernel test hosts.


## v0.3.20 — Extended Linux distribution identification (v1 groundwork)

- Add read-only CloudLinux, SUSE, Alpine, Gentoo, NixOS, Void and additional RHEL/Debian/Arch derivative identification.
- Keep all unvalidated distribution kernel installation and reboot operations blocked; AlmaLinux 8/9/10 remain the only tested automation implementation.
- Add CloudLinux-specific LVE/LTS/hybrid limitations and platform compatibility requirements. This does not claim v1.0.0-level cross-distribution support.


## v0.3.19 — Multi-distribution detection foundation

- Detect RHEL-family, Debian-family and Arch-family systems via the read-only `lksu compatibility --json` command.
- Preserve verified AlmaLinux 8/9/10 kernel update and guarded reboot support.
- **No production support for other distributions yet:** updating and rebooting remain blocked until distro-specific installation/rollback tests are completed.
- Add regression tests for fail-closed unsupported hosts; no live distribution validation was performed.

## v0.3.18 — Continuous kernel automation (maintenance-window removal)

- Remove all time-of-day restriction prompts and window evaluation, including the old 03:00/60-minute defaults. Every enabled LKSU kernel timer invocation can assess updates at any hour (15-minute systemd cadence).
- Automatically remove the retired `maintenance_window` key from existing root-only configuration on the next LKSU read. Preserve SMTP credentials, automatic install/reboot opt-ins, recovery readiness, security policy, health checks and unrelated settings.
- Keep guarded kernel RPM installation, free-space recovery, previous-kernel preservation, one-shot GRUB trial boot, provider-snapshot approval, service/URL health verification, post-boot promotion and rollback tooling unchanged.
- Refresh English console/email reports, documentation and regression tests. No direct server update, reboot or v0.3.18 live-host validation is implied by this release.

### Upgrade notes

Existing hosts that previously had a restricted window will now run **authorized** kernel install/reboot operations at any time once the release is activated and the timer fires. There is no longer a quiet-hours gate; confirm outage acceptance and existing `recovery_ready` and service-health settings before upgrading. LKSU **does not create VM snapshots**: the operator must maintain a real snapshot/provider console.

## v0.3.17 — Kernel lifecycle automation

- **Anytime eligible updates:** an explicitly unrestricted maintenance policy is evaluated every 15 minutes. Existing saved maintenance windows are preserved until an operator changes them.
- **Conservative /boot space reclaim:** when available space is below 500 MiB before an eligible kernel installation, LKSU can remove only verified obsolete kernel RPMs; active, default, most recently installed and recorded fallback kernels are protected. If no safe candidate is available, installation stops with a visible error rather than deleting a fallback.
- **Operator-visible update/reboot progress:** flushed messages show package installation, safety preflight, trial GRUB staging, systemd reboot request and post-boot verification; journalctl captures the unattended service output.
- **SMTP onboarding:** beginner steps for Postmark, SMTP2GO, custom SMTP and DNS sender verification are documented in README.

### Upgrade notes

The pinned bootstrap entry point is `v0.3.17/bootstrap.sh`. Existing installation settings, including a restricted maintenance window, are retained. To explicitly opt into 24/7 checks on an existing system run `sudo /usr/local/bin/lksu configure-automation` and answer **n** to the maintenance-window restriction prompt. The auto-reboot feature still requires confirmed external recovery readiness and healthy configured applications.

### Validation and limitations

A real AlmaLinux 9.8 VPS has completed an automatic kernel upgrade, trial reboot and post-boot verification on v0.3.16. New lifecycle output and cleanup behavior have passed CI unit tests, but their real-host integration, complete AlmaLinux 8/9/10 BIOS/UEFI compatibility and failure/recovery drills have **not** been proven. Do not interpret one successful reboot or the existence of fallback kernel RPMs as a VM snapshot or universal recovery guarantee.
