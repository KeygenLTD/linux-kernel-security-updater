# Changelog

## v0.3.17 — Kernel lifecycle automation

- **Anytime eligible updates:** an explicitly unrestricted maintenance policy is evaluated every 15 minutes. Existing saved maintenance windows are preserved until an operator changes them.
- **Conservative /boot space reclaim:** when available space is below 500 MiB before an eligible kernel installation, LKSU can remove only verified obsolete kernel RPMs; active, default, most recently installed and recorded fallback kernels are protected. If no safe candidate is available, installation stops with a visible error rather than deleting a fallback.
- **Operator-visible update/reboot progress:** flushed messages show package installation, safety preflight, trial GRUB staging, systemd reboot request and post-boot verification; journalctl captures the unattended service output.
- **SMTP onboarding:** beginner steps for Postmark, SMTP2GO, custom SMTP and DNS sender verification are documented in README.

### Upgrade notes

The pinned bootstrap entry point is `v0.3.17/bootstrap.sh`. Existing installation settings, including a restricted maintenance window, are retained. To explicitly opt into 24/7 checks on an existing system run `sudo /usr/local/bin/lksu configure-automation` and answer **n** to the maintenance-window restriction prompt. The auto-reboot feature still requires confirmed external recovery readiness and healthy configured applications.

### Validation and limitations

A real AlmaLinux 9.8 VPS has completed an automatic kernel upgrade, trial reboot and post-boot verification on v0.3.16. New lifecycle output and cleanup behavior have passed CI unit tests, but their real-host integration, complete AlmaLinux 8/9/10 BIOS/UEFI compatibility and failure/recovery drills have **not** been proven. Do not interpret one successful reboot or the existence of fallback kernel RPMs as a VM snapshot or universal recovery guarantee.
