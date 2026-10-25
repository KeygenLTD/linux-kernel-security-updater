# LKSU v1 platform support requirements

**Important:** recognition is not kernel update support. Current unattended
kernel updates and trial reboot remain supported only on AlmaLinux 8/9/10.
Other Linux systems are detected read-only and kernel mutations are denied.

## Candidate platform families

| Family | Distributions / variants | Package manager | Kernel automation |
| --- | --- | --- | --- |
| RHEL | AlmaLinux, Rocky, RHEL, CentOS Stream, Oracle Linux, Fedora, Amazon Linux, EuroLinux, OpenCloudOS, Anolis, Virtuozzo | DNF/RPM | AlmaLinux 8/9/10 only |
| CloudLinux | CloudLinux OS 8/9/10 variants | DNF/RPM, vendor packages | Not enabled |
| Debian | Debian, Ubuntu, Mint, Pop!_OS, elementary, Kali, Raspbian, Proxmox, Devuan | APT/DPKG | Not enabled |
| SUSE | openSUSE Leap/Tumbleweed, SLES, SLED | Zypper/RPM | Not enabled |
| Arch | Arch, Manjaro, EndeavourOS | Pacman | Not enabled |
| Alpine | Alpine, postmarketOS | APK | Not enabled |
| Gentoo | Gentoo, Funtoo | Portage | Not enabled |
| Nix | NixOS | Nix generations | Not enabled |
| Void | Void Linux | XBPS | Not enabled |

This is not an exhaustive list of Linux distributions or a guarantee that a
named derivative behaves identically to its family.

## Hard safety gates before enabling each backend

1. Exact supported distribution ID and release, no implicit ID_LIKE match.
2. Native kernel package detection and security-advisory mapping with CVEs.
3. Exact installed/current/pending kernel checks, package signatures and repository trust.
4. Preserve real previous kernel and all required modules before transaction.
5. Bootloader/firmware-specific trial boot and verified persistent fallback,
   including Secure Boot, UKI, BIOS/UEFI and provider-managed boot cases.
6. External snapshot and functional provider recovery console confirmed.
7. Correct runtime application, storage and network health checks before reboot.
8. Post-boot kernel and service verification, failure alert and operator recovery path.
9. Independent disposable VM tests for successful boot, failed boot, no space,
   RPM/APT conflict, interrupted installation and rollback.
10. No automatic activation from a read-only detection change.

## CloudLinux-specific constraints

CloudLinux OS 9+ uses an AlmaLinux-based kernel by default, but CloudLinux LTS
kernels and kmod-lve dependencies have distinct upgrade paths. CloudLinux OS 8
can use CloudLinux-specific/hybrid/LTS kernel packages. Never swap between
these families or remove LVE kernel modules as a generic kernel update.
A kernel with the correct version number alone does not prove application
or LVE functionality. Require explicit compatibility checks.

Official reference: https://docs.cloudlinux.com/cloudlinuxos/cloudlinux_os_kernel/

## Releasing v1.0.0

Only publish v1.0.0 as generally supported when its documented distro/kernel
matrix is backed by actual install, trial reboot, post-boot and rollback
evidence. Until then, retain pre-1.0 versioning and release explicit partial
milestones. Do not claim a CVE is remediated for a host without authoritative
vendor advisory mapping and verification that a patched kernel is running.
