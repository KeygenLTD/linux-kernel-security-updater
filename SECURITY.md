# LKSU Security Policy and Review

LKSU is a privileged AlmaLinux kernel/boot-update agent. Its primary risks are **privileged code execution via supply-chain compromise**, accidental reboot/boot failure, exposure of SMTP/fleet credentials, and misuse or compromise of the optional fleet dashboard. A passing unit suite or one working web host does not establish that the kernel reboot and recovery paths are fully validated.

## Current review (v0.3.17)

| Area | Safeguard | Residual risk |
| --- | --- | --- |
| Root subprocesses | Commands are argument arrays (no shell interpolation); inherited PATH/Python/loader hooks are sanitized | Compromised root, DNF repos or system binaries remain trusted execution sources |
| Credential/config storage | Root-owned regular file at `/etc/lksu/config.json`, required mode 0600, no symbolic/hard links | Root can read credentials; protect backups and logs |
| State writes | Exclusive temporary file in trusted state directories and atomic replace | A compromised root user can change state |
| LKSU auto-update | Only stable versioned GitHub Release wheel, fixed repository URLs, GitHub-provided SHA-256, root-controlled version directories, rollback of launcher links | GitHub checksum is **not independent publisher signing**; a malicious or compromised release remains code execution as root |
| Kernel auto-reboot | Opt-in, maintenance window, operator-confirmed snapshot+provider console, passing service/URL health checks, old GRUB entry and one-shot trial | Hardware, bootloader or kernel failures can still require a real provider console; no automatic recovery from every non-boot |
| Optional fleet client/server | Authenticated HMAC payloads, HTTPS outside loopback, bound request body and timeouts, TLS required on non-loopback listener | No anti-replay nonce store, reverse-proxy hardening, traffic quotas or full web penetration test; dashboard access must be restricted |

## Required operator hardening

Keep GitHub account and release-writing permissions minimal, enable MFA/passkeys/security keys and branch protection, require code review and protect CI credentials. Pin dependency and GitHub Action revisions as appropriate, audit every release and consider independently signed artifacts/attestations before large-scale unattended rollout.

Store the SMTP credential in a dedicated account; restrict `/etc/lksu/` and `/var/lib/lksu/` to root; do not paste configuration files, tokens, snapshots or private logs in public issues. Run the optional fleet collector behind an authenticated TLS reverse proxy and network restrictions, and retain backups of fleet data.

Do not falsely attest to external snapshot readiness. Test the GRUB one-shot boot, kernel promotion, rollback, and failed-health recovery in an isolated AlmaLinux VM using both UEFI and BIOS as relevant. LKSU cannot guarantee recovery if the host fails to boot or the provider console is unavailable.

## Responsible reporting

Please report suspected vulnerabilities privately via the repository's GitHub **Security advisories** page; never disclose exploitable details or secrets in public issues. Include the affected version, AlmaLinux release, architecture, boot mode, a minimal safe reproduction and impact. Security fixes are best-effort; no long-term support designation has been made.
