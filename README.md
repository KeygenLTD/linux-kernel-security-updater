# Linux Kernel Security Updater (LKSU)

<p align="center">
  <strong>Linux kernel platform coverage</strong>
</p>
<p align="center">
  <a href="#multi-distribution-roadmap-in-development"><img alt="AlmaLinux — kernel updates" src="https://img.shields.io/badge/AlmaLinux-Kernel_Updates-168B4C?style=flat-square&logo=almalinux&logoColor=white"></a>
</p>
<p align="center">
  <a href="docs/platform-support.md"><img alt="CloudLinux — detection only" src="https://img.shields.io/badge/CloudLinux-Detection_Only-555555?style=flat-square"></a>
  <a href="docs/platform-support.md"><img alt="Rocky Linux — detection only" src="https://img.shields.io/badge/Rocky_Linux-Detection_Only-555555?style=flat-square&logo=rockylinux&logoColor=white"></a>
  <a href="docs/platform-support.md"><img alt="Red Hat Enterprise Linux — detection only" src="https://img.shields.io/badge/RHEL-Detection_Only-555555?style=flat-square&logo=redhat&logoColor=white"></a>
  <a href="docs/platform-support.md"><img alt="CentOS — detection only" src="https://img.shields.io/badge/CentOS-Detection_Only-555555?style=flat-square&logo=centos&logoColor=white"></a>
  <a href="docs/platform-support.md"><img alt="Oracle Linux — detection only" src="https://img.shields.io/badge/Oracle_Linux-Detection_Only-555555?style=flat-square&logo=oracle&logoColor=white"></a>
  <a href="docs/platform-support.md"><img alt="Fedora — detection only" src="https://img.shields.io/badge/Fedora-Detection_Only-555555?style=flat-square&logo=fedora&logoColor=white"></a>
  <a href="docs/platform-support.md"><img alt="Amazon Linux — detection only" src="https://img.shields.io/badge/Amazon_Linux-Detection_Only-555555?style=flat-square&logo=amazonaws&logoColor=white"></a>
  <a href="docs/platform-support.md"><img alt="Ubuntu — detection only" src="https://img.shields.io/badge/Ubuntu-Detection_Only-555555?style=flat-square&logo=ubuntu&logoColor=white"></a>
  <a href="docs/platform-support.md"><img alt="Debian — detection only" src="https://img.shields.io/badge/Debian-Detection_Only-555555?style=flat-square&logo=debian&logoColor=white"></a>
  <a href="docs/platform-support.md"><img alt="Linux Mint — detection only" src="https://img.shields.io/badge/Linux_Mint-Detection_Only-555555?style=flat-square&logo=linuxmint&logoColor=white"></a>
  <a href="docs/platform-support.md"><img alt="Proxmox — detection only" src="https://img.shields.io/badge/Proxmox-Detection_Only-555555?style=flat-square&logo=proxmox&logoColor=white"></a>
  <a href="docs/platform-support.md"><img alt="openSUSE — detection only" src="https://img.shields.io/badge/openSUSE-Detection_Only-555555?style=flat-square&logo=opensuse&logoColor=white"></a>
  <a href="docs/platform-support.md"><img alt="Arch Linux — detection only" src="https://img.shields.io/badge/Arch_Linux-Detection_Only-555555?style=flat-square&logo=archlinux&logoColor=white"></a>
  <a href="docs/platform-support.md"><img alt="Manjaro — detection only" src="https://img.shields.io/badge/Manjaro-Detection_Only-555555?style=flat-square&logo=manjaro&logoColor=white"></a>
  <a href="docs/platform-support.md"><img alt="Alpine — detection only" src="https://img.shields.io/badge/Alpine-Detection_Only-555555?style=flat-square&logo=alpinelinux&logoColor=white"></a>
  <a href="docs/platform-support.md"><img alt="Gentoo — detection only" src="https://img.shields.io/badge/Gentoo-Detection_Only-555555?style=flat-square&logo=gentoo&logoColor=white"></a>
  <a href="docs/platform-support.md"><img alt="NixOS — detection only" src="https://img.shields.io/badge/NixOS-Detection_Only-555555?style=flat-square&logo=nixos&logoColor=white"></a>
  <a href="docs/platform-support.md"><img alt="Void Linux — detection only" src="https://img.shields.io/badge/Void_Linux-Detection_Only-555555?style=flat-square&logo=voidlinux&logoColor=white"></a>
</p>

<p align="center"><small><strong>Kernel Updates</strong> = existing AlmaLinux 8/9/10 implementation. <strong>Detection Only</strong> = recognition only; no kernel installation or automatic reboot on these platforms.</small></p>

![LKSU kernel update, verification and fallback illustration](docs/assets/lksu-hero.png)

> **Status: v0.3.21 early preview.** CI unit tests target Python 3.9, 3.11 and 3.13. One AlmaLinux 9.8 VPS successfully completed a kernel RPM update, automatic trial reboot and post-boot service verification with an earlier LKSU release. That does **not** validate v0.3.21 on a production host, all AlmaLinux 8/9/10 BIOS/UEFI/recovery variants, or automatic kernel cleanup. Confirm an external snapshot, provider console and service checks before unattended reboot.

Early production-oriented release for **AlmaLinux 8, 9 and 10**. LKSU uses the distribution's enabled DNF repositories. It does not enable testing repositories, select a CVE-specific build, or download arbitrary RPMs. It requests automatic reboot only after opt-in and safety checks.

See [platform coverage and safety gates](docs/platform-support.md) for CloudLinux, Ubuntu, Debian, SUSE, Arch, NixOS and other families. Detection does not authorize kernel changes.

## Multi-distribution roadmap (in development)

Run `lksu compatibility --json` to inspect the current Linux distribution and the
available kernel/update/boot backend **without making system changes**.

| Distribution family | Detection | Unattended kernel update | Reboot and rollback |
| --- | --- | --- | --- |
| AlmaLinux 8/9/10 | Yes | Existing implementation | Existing guarded trial boot |
| Rocky Linux / RHEL / CentOS Stream / Fedora | Yes | Not yet validated; blocked | Blocked |
| Ubuntu / Debian | Yes | APT adapter not yet implemented; blocked | Blocked |
| Arch Linux | Yes | Pacman adapter not yet implemented; blocked | Blocked |

This capability inspection does **not** imply those platforms are supported.
We will only unlock automatic updates after distro-specific kernel packaging,
transaction, bootloader, snapshot/recovery and post-boot tests pass. A distro
that cannot be safely identified or recovered always fails closed.
No SSH access to production servers was used to develop this feature.

## Safety model

- The interactive one-command installer defaults to `all-stable` automatic kernel updates and offers guarded automatic reboot; the operator can decline. Direct/manual setups must configure a kernel policy explicitly. The daily read-only check does not send routine emails.
- `security-only` reads DNF security updateinfo and reports advisory IDs, severity, affected kernel packages and CVEs. `all-stable` permits all kernel updates from enabled repositories.
- Before installation LKSU checks AlmaLinux version, root privileges, required tools, `/boot` free space, a GRUB configuration, the running kernel's image, and its installed RPM. Its disk threshold is 500 MiB; host-specific layouts may require more.
- Installation overrides DNF's `installonly_limit` to preserve installed kernels. LKSU checks that the running kernel's RPM and boot image still exist, then records the previous kernel. It does **not** create a full boot, VM, filesystem, or data backup.
- LKSU checks for kernel updates **24/7, every 15 minutes** when `lksu-maintenance.timer` is enabled. There is no clock-based maintenance window. Installing and rebooting remain separately configurable and are gated by actual eligibility and recovery checks.
- A trial reboot keeps the old kernel as the persistent GRUB default and selects the new kernel once with `grub2-reboot`. Successful service and HTTP/HTTPS health checks promote the new kernel.
- Agents can send HMAC-signed reports over HTTPS to the SQLite-backed `lksu-fleet` collector and bearer-token-protected web dashboard.
- Optional Security Watch reports LKSU/config integrity changes, inactive configured security services, non-enforcing SELinux, repeated SSH failures and successful root SSH logins. It never edits files, blocks addresses or removes users.
- The fleet dashboard marks a server silent/stale when its signed heartbeat is older than the configured threshold.
- `lksu select-old` selects the previous kernel as the default for the **next** boot and verifies GRUB's selection. It does not cause a reboot or guarantee recovery from an unbootable machine. A failed boot may require a provider console and manual GRUB selection. Keep a current provider snapshot and console access.
- A pending update blocks a second install until successful post-boot verification. Failed verification leaves the pending state and requires investigation.

## Install on a test VM first

The recommended path is the interactive one-command installer below. Manual installation is also possible. The current setup wizard supports Postmark, SMTP2GO or custom authenticated SMTP.

```bash
sudo ./install.sh
sudo /usr/local/bin/lksu configure
sudo systemctl enable --now lksu.timer lksu-maintenance.timer lksu-security-watch.timer
sudo systemctl enable lksu-verify.service
sudo /usr/local/bin/lksu scheduled
systemctl list-timers lksu.timer lksu-maintenance.timer
```

## One-command setup (recommended)

For the pinned **v0.3.20 release** on AlmaLinux 8/9/10 (only after the GitHub Release wheel has been published and verified):

```bash
curl -fsSL https://raw.githubusercontent.com/KeygenLTD/linux-kernel-security-updater/v0.3.21/bootstrap.sh | sudo bash
```

This installs LKSU, asks for the report email and provider settings, configures timers, and immediately attempts an eligible kernel installation if automatic updates are selected. A trial reboot can occur when explicitly enabled and after every recovery and health gate passes.

## What's new in v0.3.18

1. **No time-of-day restriction.** `lksu-maintenance.timer` polls at 00, 15, 30 and 45 minutes of every hour. Eligible kernel upgrades can install at any check when `automatic_updates=true` and the install policy authorizes them. Guarded reboot requires separate opt-in and passing recovery and health checks. The old maintenance-window prompts and settings are removed; upgrades discard only the obsolete scheduling key.
2. **Conservative /boot cleanup.** Before an authorized kernel update, if `/boot` free space is below **500 MiB**, LKSU can remove exact RPM packages belonging to an obsolete kernel while retaining the active/default kernel, the two most recently installed kernels and LKSU-tracked recovery versions. No safe candidate = no deletion, error and operator review. This is **not** a guarantee that 500 MiB accommodates any custom initramfs; test nonstandard layouts.
3. **Visible progress before reboot.** Immediately flushed `LKSU [UPDATE]`, `LKSU [REBOOT]` and `LKSU [VERIFY]` messages explain RPM installation, health checks, GRUB trial staging and the systemd reboot request. PuTTY/SSH may disconnect when reboot begins; boot success is confirmed **only after** post-boot checks. Messages also appear in journalctl when LKSU runs unattended.

**Upgrading from v0.3.17:** Existing `/etc/lksu/config.json` values for SMTP, `automatic_updates`, `automatic_reboot`, installation policy, recovery readiness, notification preferences and service/URL checks are preserved. The obsolete `maintenance_window` field is removed automatically when the upgraded LKSU reads the configuration; its former time restriction is no longer enforced. A 15-minute timer remains responsible for continuous checks. This change permits operations outside prior quiet hours **only for previously authorized automation**. Do not re-run `initialize` for a status check: it can install a kernel and reboot an authorized server.

## Beginner's email setup: Postmark, SMTP2GO or your own SMTP

**Do I need to install an email server? No.** LKSU only needs access to an **outgoing SMTP service**: a provider that sends alert emails for you. You do not need to install Postfix, open inbound mail ports, or run a mailbox server. The installer asks for an email address and the credentials of that SMTP service.

**Two things to understand before starting:**

- **Report email** = the address where you receive LKSU alerts. **In the current LKSU version, this same address is also used as the From (sender) address.** Therefore, choose an address you can receive mail at **and** are allowed to send from using the provider. For example, `alerts@example.com` must be a real mailbox (or a working forwarding address) under a verified sending domain; do not literally enter the example address.
- **SMTP username/password** = credentials issued by the sending provider. They are usually **not** your provider website login and should never be your main account password. The setup wizard hides passwords while you type.

**Choose ONE of the following:**

| Provider | Good for | What LKSU needs | Where to start |
| --- | --- | --- | --- |
| **Postmark** | Simple transaction/alert messages | Postmark **Server API Token** | [Postmark sign-up](https://account.postmarkapp.com/sign_up) |
| **SMTP2GO** | Dedicated SMTP username/password; a free option for smaller volumes | SMTP2GO **SMTP User** credentials | [SMTP2GO](https://www.smtp2go.com/) |
| **Custom SMTP** | An existing mail hosting service or mailbox with SMTP support | SMTP hostname, port, username, app password/password | Your mail provider's SMTP settings page |

The providers' free-plan allowances and approval policies can change. Check [Postmark pricing](https://postmarkapp.com/pricing) and [SMTP2GO pricing](https://www.smtp2go.com/pricing/) before relying on them.

### Option A — Postmark, step by step

1. Visit **[Postmark sign-up](https://account.postmarkapp.com/sign_up)**, create an account (the form asks for a work email) and confirm the registration email.
2. In Postmark, select an existing **Server** or create one called something like `LKSU alerts`. (A Postmark "Server" is a dashboard grouping; it is **not** a VPS you need to set up.)
3. Verify the email address you intend to put in LKSU's **Report email** field:
   - Go to **Sender Signatures** and add/verify a **Sender Signature** for that exact address; follow the confirmation message.
   - Or verify your own sending **Domain**. Postmark will show DKIM/Return-Path DNS records. Copy the values Postmark displays into the DNS manager for your domain (for example Cloudflare), then use Postmark's **Verify** action. **Do not guess DNS values.**
   - A domain you control is the safest choice. Sending from a personal `@gmail.com` or `@yahoo.com` address through Postmark is generally not an appropriate domain-authentication setup.
4. Open **Servers → your server → API Tokens** and copy the **Server API Token**. **Do not use the Account API Token**. The Server API Token works as **both the SMTP username and SMTP password** with LKSU's built-in Postmark option.
5. Ensure SMTP access is enabled for the Postmark server / transactional stream. If sending to an external mailbox is blocked on a new account, review your account approval/trial restrictions in Postmark first.
6. Run the LKSU installer (shown above), then answer the mail prompts **like this** (replace the examples with real values):

   ```text
   Report email: alerts@example.com
   Mail provider [postmark/smtp2go/custom] (default postmark): postmark
   Postmark Server Token: [paste YOUR server token; input is hidden]
   ```

LKSU automatically uses **`smtp.postmarkapp.com`**, **port `587`** and **STARTTLS** for this option. You do not need to enter these values separately. Postmark's [SMTP documentation](https://postmarkapp.com/developer/user-guide/send-email-with-smtp) and [token documentation](https://postmarkapp.com/support/article/1008-what-are-the-account-and-server-api-tokens) explain the details.

### Option B — SMTP2GO, step by step

1. Open **[SMTP2GO](https://www.smtp2go.com/)**, create an account using an email address on a domain you control (its current signup form does **not** accept public Gmail/Yahoo addresses) and verify the registration email. Complete any requested account/phone verification.
2. In its dashboard go to **Sending → Verified Senders → Sender domains**. Add the domain you own, e.g. `example.com`.
3. SMTP2GO will show the **DNS CNAME records** needed to authenticate that domain. Open the DNS settings at your domain provider (such as Cloudflare), create the records **exactly as shown**, and return to SMTP2GO to verify the sender domain. See [the official verified-sender guide](https://support.smtp2go.com/hc/en-gb/articles/115004408567-Verified-Senders). Domain verification may take some time.
4. Go to **Sending → SMTP Users**, choose **Add SMTP user**, and create a dedicated user such as `lksu-alerts` with a strong unique password. This is **not** the password used to log in to the SMTP2GO website. Save the SMTP username and password somewhere secure. See [the official SMTP User guide](https://support.smtp2go.com/hc/en-gb/articles/13645646122777-SMTP-User-Authentication).
5. In LKSU's installer enter:

   ```text
   Report email: alerts@example.com
   Mail provider [postmark/smtp2go/custom] (default postmark): smtp2go
   SMTP2GO username: [your SMTP2GO SMTP user]
   SMTP2GO password: [your SMTP user's password; input is hidden]
   ```

LKSU automatically uses **`mail.smtp2go.com`**, **port `587`**, **STARTTLS**. You do **not** have to create a mail server on the VPS. The SMTP2GO [official connection guide](https://www.smtp2go.com/setup/) lists alternate ports in case outbound port 587 is blocked. Since LKSU's built-in SMTP2GO option fixes port 587, an alternate port requires choosing **custom** instead.

### Adding sender DNS records in Cloudflare (Postmark or SMTP2GO)

If your domain's DNS is managed by **Cloudflare**, this is where you enter the verification records shown by your email provider:

1. Sign in to **[Cloudflare Dashboard](https://dash.cloudflare.com/)**.
2. Choose your **domain**, then go to **DNS → Records**.
3. In another tab, keep Postmark's **Domain / DNS Settings** or SMTP2GO's **Verified Senders** screen open. It shows each record's **Type**, **Name/Host** and **Value/Target**.
4. Select **Add record** in Cloudflare. Choose **TXT** or **CNAME** exactly as specified by your email provider. Paste the exact **Name** and **Content** values it displays, then save. For CNAME verification records, use **DNS only** rather than the orange proxied cloud when that option is offered.
5. Repeat for the other verification records your provider requires. **Do not delete or replace existing MX, SPF, DKIM or unrelated records.** If a conflicting record already exists, stop and consult your mail provider's guidance instead of blindly overwriting it.
6. Return to Postmark/SMTP2GO and click **Verify / Check DNS**. DNS verification is not always immediate; retry after DNS propagation. Do not proceed until the required sender/domain shows as verified.

**You do not need to transfer your domain, change its nameservers or move your mailbox to Postmark/SMTP2GO.** Verifying a sending domain generally only adds the required DNS authentication records.

### Option C — Your existing email provider (custom SMTP)

If you already pay for email hosting, ask your mail provider or read its official support page for the **outgoing SMTP server address**, **SMTP port**, **SMTP username** and **password/app password**. This is about **sending** messages; IMAP/POP3 settings for **receiving** messages are not used by LKSU.

Example **only if your provider supports these settings**:

```text
Report email: alerts@example.com
Mail provider [postmark/smtp2go/custom] (default postmark): custom
SMTP host: smtp.your-provider.example
SMTP port [465]: 587
SMTP username: alerts@example.com
SMTP password or app password: [provider-issued password; input is hidden]
```

For example, a compatible personal Gmail account may use **`smtp.gmail.com`**, **port `587` (STARTTLS)**, the Gmail address as username, and a Google **app password** (when that account is eligible). Enable two-step verification first. Use [Google's official app-password instructions](https://support.google.com/accounts/answer/185833?hl=en); **do not enter your normal Google account password**. Gmail and some organization-managed Google Workspace accounts may not expose app passwords, so a dedicated transactional SMTP provider is generally easier for a production server.

**TLS and ports:** LKSU uses implicit TLS when you enter **465**, and requires **STARTTLS** on other ports such as **587**. Use the port and encryption mode that your provider supports; never disable certificate verification to work around an error.

### What to type in the other LKSU setup prompts

After email setup, LKSU asks separate questions about updating the kernel and restarting the machine. These **can change your server**:

| Setup question | Explanation |
| --- | --- |
| `Install available kernel updates on setup and automatically thereafter?` | `y` authorizes real kernel package installation, including during the first setup. |
| `Automatically install verified LKSU releases?` | `y` allows updates to the LKSU application itself when a newer published release is available. |
| `Email only when updates succeed or fail?` | `y` means event-based alerts rather than a daily "nothing changed" email. |
| `Automatically reboot after installing a kernel when recovery checks pass?` | `y` permits real unattended downtime. Prepare a provider snapshot and console access first. |
| `Services to verify after reboot` | Enter real application services (e.g. `mariadb,nginx`) or accept detected active applications. Do not use a made-up name. |

### Check SMTP connectivity and alert delivery

1. **First check the sender in your provider dashboard:** sender/domain is verified, SMTP is enabled, and (if required) sending approval is granted.
2. **Check the provider's server/port from the VPS** (replace the host if needed):

   ```bash
   # Postmark on port 587; use mail.smtp2go.com for SMTP2GO.
   openssl s_client -starttls smtp -connect smtp.postmarkapp.com:587 -servername smtp.postmarkapp.com -brief </dev/null
   ```

   A successful TLS handshake means the server could reach the provider securely. It does **not** prove that your SMTP credentials are valid or that a message was delivered.
3. **Check LKSU's read-only status**:

   ```bash
   sudo lksu scheduled
   systemctl list-timers --all 'lksu*'
   ```

   **Important: `lksu scheduled` does not send a test email.** LKSU intentionally only sends alert emails after an actual update, verified boot transition, or reportable failure. Do not deliberately trigger an update or reboot merely to test email.
4. After a **real** LKSU notification event, check your inbox **and spam/junk folder**, look at the provider's sending/activity logs, and inspect the LKSU journal if sending failed:

   ```bash
   journalctl -u lksu-maintenance.service -u lksu-verify.service -n 100 --no-pager
   ```

**Common problems:**

| Symptom | Likely cause and next check |
| --- | --- |
| `535` or `Authentication failed` | Incorrect provider SMTP credentials. Postmark needs the **Server** token, not the Account token; SMTP2GO needs an **SMTP User**. |
| `Sender Signature Not Found` / `sender not verified` | The `Report email` is also the From address; verify that exact sender/domain at the provider. |
| `Connection timed out` | VPS egress firewall/provider blocks the SMTP port, or hostname/port is wrong. Check provider documentation and outbound connectivity. |
| `TLS/SSL` error | Wrong port/encryption combination; 587 normally uses STARTTLS, while 465 uses implicit TLS only if supported. |
| No email after `lksu scheduled` | **Normal:** routine read-only checks do not send email. |
| Provider accepted email, but nothing in inbox | Inspect provider activity, spam/junk folder, recipient address and provider restrictions. |

**Secrets and safety:** LKSU stores mail settings in root-only `/etc/lksu/config.json` (mode `0600`). This is a local configuration file containing an SMTP secret, **not** a vault. Never paste tokens/passwords into GitHub issues, README examples, chat messages, screenshots or public logs; never commit the config file. Prefer a separate SMTP credential for each server. If credentials leak, revoke/rotate them at the provider. Because the current Report email doubles as From, make sure that address is a permitted sender. If you change SMTP settings after installation, back up and review existing automation settings before re-running the full `sudo lksu configure` wizard, which replaces configuration.

## Watching kernel installation and automatic reboot

Starting with **v0.3.17**, the interactive installer and LKSU maintenance runs print **flushed progress events** before starting DNF, before preparing a one-time GRUB boot, and immediately before asking systemd to restart the server. Progress appears on stderr, so `lksu ... --json` stdout stays valid JSON.

Example of messages during a real, authorized update (not a simulation of reboot success):

```text
LKSU [INIT] Starting first managed kernel maintenance pass...
LKSU [CHECK] Checking installed kernel versions, repositories and /boot space...
LKSU [UPDATE] Eligible kernel upgrade found; installing repository RPM packages with DNF. Please do not close this session.
LKSU [UPDATE] Kernel RPM installation finished. Running: OLD_KERNEL; next-boot candidate: NEW_KERNEL.
LKSU [REBOOT] Checking operator-approved recovery readiness and application health...
LKSU [REBOOT] Pre-reboot application checks passed (N). Recovery prerequisites were confirmed by the operator.
LKSU [REBOOT] Preparing one-time GRUB boot with previous-kernel fallback...
LKSU [REBOOT] One-time GRUB boot staged for NEW_KERNEL; persistent fallback: OLD_KERNEL.
LKSU [REBOOT] Requesting system reboot NOW for one-time trial kernel NEW_KERNEL. SSH may disconnect. Boot success is verified only after the server returns.
```

When the server reboots, **SSH/PuTTY disconnecting is normal**. That disconnection is **not** proof the new kernel booted successfully. After reconnecting, inspect the verification log and running/default kernels:

```bash
uname -r
grubby --default-kernel
journalctl -b -u lksu-verify.service -n 60 --no-pager
sudo /usr/local/bin/lksu scheduled
```

For an unattended timer update, read the actual progress in the system journal (no routine email or active SSH window is required):

```bash
journalctl -u lksu-maintenance.service -u lksu-verify.service --no-pager -n 100
```

**Important:** Progress output is not a safety check or a guarantee of recovery. LKSU still requires real configured application checks, an operator-confirmed external snapshot/provider recovery path and successful post-boot verification. Do **not** trigger `initialize` or `maintenance` merely to see the messages: those commands can install kernels and reboot production servers. Use `scheduled` for a safe read-only check. Progress messages were introduced in v0.3.17 and remain available.

## Automatic kernel lifecycle and LKSU self-updates

**Two update channels:** The daily `lksu scheduled` timer is read-only. The enabled `lksu-maintenance.timer` checks every 15 minutes, 24/7, and installs eligible kernel RPMs only if `automatic_updates=true` and the configured policy permits it. A newer installed GRUB default differing from the running kernel is reported as **REBOOT REQUIRED**, even when DNF has 0 upgrades. With separate guarded reboot authorization, LKSU can adopt an already-installed newer kernel after validating RPMs, boot images, initramfs, native RPM version ordering and GRUB entries.

**Unattended kernel reboots are guarded:** Before LKSU stages a one-shot GRUB trial reboot, it requires `automatic_reboot=true`, `recovery_ready=true` (manual confirmation of an external snapshot and functional provider console), at least one configured and passing service or HTTP health check, and an enabled `lksu-verify.service`. The old kernel stays the persistent default until post-boot verification succeeds. A failure requires investigation; a preserved kernel alone is not a full server snapshot. Existing `/var/lib/lksu/state.json` entries awaiting verification block repeat installation, and trials are not automatically repeated. The installer enables the verification **service**; after setup the authorized kernel maintenance process automatically stages and requests a reboot when safety checks pass.

**LKSU itself can update automatically, independently of kernel updates.** Daily `lksu-self-update.timer` invokes `lksu self-update-scheduled`. It is inert until `automatic_lksu_updates=true` is explicitly set in root-owned `/etc/lksu/config.json` (file mode 0600). Once enabled, LKSU checks the repository's latest non-draft GitHub Release and installs a newer version only when it has an exact-match wheel asset and GitHub-provided SHA-256 digest. It rejects mismatches, unrecognized URLs, pre-releases, unsigned-by-digest assets and downgrades. New versions are staged in separate virtual environments under `/opt/lksu/releases/` and activated through `/opt/lksu/current`; old releases and the original binary entrypoints are kept for recovery. Wheel digest verification establishes artifact integrity against GitHub's release metadata; it is **not** independent publisher-code signing. Protect repository/release permissions accordingly.

One-time operator commands after applying this release:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lksu-self-update.timer
sudo systemctl enable lksu-verify.service
sudo lksu self-update-check                  # read-only, requires a published GitHub release
sudo systemctl list-timers --all 'lksu*'
```

Enable **LKSU application updates** by editing the existing config to set `"automatic_lksu_updates": true`, while keeping mode 0600. Kernel automation and automatic reboot have **separate** flags. Do not set `recovery_ready=true` until a recovery drill and backup are complete. For visibility, `sudo lksu scheduled` displays the boot status without installing or rebooting. The installer upgrades the application's own systemd unit files but preserves the existing configuration. A release is eligible only **after** its Git tag and GitHub Release wheel have been published; publishing tags is a maintainer action rather than a server-initiated process.

## First-install kernel update and automatic reboot

When the interactive setup enables **automatic kernel updates**, the one-command bootstrap runs `lksu initialize` after installing systemd units and enabling timers. This can immediately perform a real DNF kernel transaction. If a newer default kernel is already installed, LKSU reports its pending reboot instead of redownloading it.

For **automatic reboots**, the operator must opt in and confirm an external snapshot and provider-console recovery access. LKSU requires at least one valid passing service/HTTP check, enabled `lksu-verify.service`, verified RPM/GRUB images and an old recoverable boot entry before a one-shot trial boot and reboot. Failed guards block reboot. The initial-run marker prevents reinstalling from repeating a real kernel installation/reboot.

After setup, the daily `lksu scheduled` job remains read-only. The `lksu-maintenance.timer` runs every 15 minutes at all hours; automatic installation and reboot depend exclusively on their separate opt-ins and safety preflight, not the clock. The old kernel RPM and persistent GRUB fallback are preserved. **LKSU does not create a disk or VM snapshot.**

To change kernel automation without touching SMTP credentials run `sudo lksu configure-automation`. To run the first managed installation explicitly, run `sudo lksu initialize`. This command may install a real kernel update and **request an immediate server reboot** if all opt-ins and safeguards are satisfied; it is not a dry run. Use `sudo lksu scheduled` for read-only observation. Details are available via `lksu scheduled --json`.

## Console output and installer preferences

By default, LKSU prints a compact English operator summary rather than a JSON advisory dump. `lksu scheduled`, `lksu check` and `lksu maintenance` display the running kernel, intended boot kernel, reboot need, update/advisory counts, the 15-minute 24/7 scan cadence and next action. Advisory counts alone do not establish vulnerability. Use `--json` for machine-readable details.

For a **new installation**, the interactive `lksu configure` setup asks whether verified LKSU application releases should be installed automatically, with a yes default. For an **existing installation** with no recorded self-update preference, the bootstrap installer asks this question once without discarding configured SMTP credentials or kernel policy. When no interactive terminal is available, the installer does not silently opt in. Reinstalling with an explicit `true` or `false` preference keeps it.

`sudo lksu configure-self-update` changes just that self-update preference, avoiding the need to enter mail credentials again. The installer provisions the daily self-update timer automatically. A new release must still be published as a GitHub Release wheel, pass digest checks, and have a version newer than the one running before it can be activated. LKSU kernel auto-install and reboot settings remain separate.

## System RPM bindings and automatic boot adoption (v0.3.17)

LKSU runs from a versioned Python virtual environment. AlmaLinux's `python3-rpm` native bindings are not installed into that environment, so the kernel version comparator calls **`/usr/bin/python3`**, where the OS package supplies native RPM EVR ordering. Do not install RPM bindings into LKSU's venv or use string comparison as a substitute. On the host, diagnose the binding using `/usr/bin/python3 -c 'import rpm; print("RPM OK")'`. The venv's `import rpm` may fail normally.

When automatic reboot is selected, LKSU suggests currently running, enabled application services regardless of hosting software. Operators can retain or replace these checks, or use HTTP(S) URLs. Missing checks prevent automatic reboot configuration. `lksu configure-automation` updates install/reboot preferences without resetting SMTP, and ensures the 15-minute kernel timer is enabled. It never asks for hours or a time window. Guarded reboot still needs true snapshot/provider-console readiness, pre-reboot health and successful post-boot verification; LKSU cannot recover from a host that fails to boot.

## Automatic low-space kernel cleanup

When an eligible automatic kernel update is ready but free space in `/boot` is below **500 MiB**, LKSU can remove obsolete kernel RPMs without making the operator manually run DNF cleanup commands. This is conditional housekeeping, not a daily purge: read-only `check` / `scheduled` remain available even below that threshold; **no eligible update means no deletion**.

The guarded cleanup retains **at least two kernel-core versions**, the currently running kernel, the GRUB default, the two most recently installed kernels, and any LKSU-tracked rollback or last-known-good kernel. If the running kernel differs from the default, a kernel transition is pending, RPM metadata is ambiguous, or an RPM dependency test fails, cleanup stops rather than guessing. It removes only packages that exactly match the selected obsolete release (kernel/core/modules families), disables DNF automatic dependency cleanup, and verifies the running/default kernels and minimum retained count afterward. The standard kernel installation and one-shot rollback protections still apply.

**Limitations:** The 500 MiB threshold is a minimum preflight value, not a universal guarantee for unusually large initramfs or custom `/boot` layouts. LKSU does not remove a fallback kernel merely to free space. Failed cleanup or insufficient free space remains a reported error requiring operator attention. Automatic deletion of kernels is a privileged operation; validate on nonproduction AlmaLinux 8/9/10 systems before relying on it in production.

## 24/7 kernel update and immediate guarded reboot

On first setup and in `lksu configure-automation`, there is **no maintenance-window prompt**. Kernel polling runs every 15 minutes, 24 hours a day. LKSU installs eligible updates from enabled DNF repositories only if `automatic_updates=true` and the policy allows them; if `automatic_reboot=true`, it attempts a one-time guarded GRUB trial boot immediately after successful preflight. A previously installed newer kernel pending restart is handled using the same safeguards.

**Important:** 24/7 polling is not instant discovery; repositories must publish updates first. Reboot interrupts service, and the provider snapshot, console access, kernel fallback, pre/post-boot health checks and deduplicated notifications remain required. The legacy time-window field is ignored and migrated away; missing recovery readiness or failed health checks still block automatic reboot. `sudo lksu scheduled` is read-only, while `sudo systemctl start lksu-maintenance.service` can install and reboot.

## Fully automatic kernel update and reboot

LKSU is an **AlmaLinux system tool, not a CyberPanel plugin**. Once configured, the sequence is:

1. The enabled `lksu-maintenance.timer` checks around every 15 minutes, all day and night, without routine email.
2. If automatic installation is enabled and the chosen kernel policy allows it, an eligible DNF kernel upgrade is installed regardless of local time. An already-installed newer kernel can be adopted without redownloading.
3. If `automatic_reboot=true` and all recovery/health prerequisites pass, LKSU preserves the previous kernel as the persistent GRUB fallback, schedules the new kernel for a one-time trial boot, and calls `systemctl reboot` itself. **No per-update SSH reboot command or additional user approval is needed.**
4. After the server starts, the enabled `lksu-verify.service` checks the running kernel and the configured service/HTTP health checks before promoting the new kernel as the persistent default. Only actual update/verification/failure events send English email.
5. If a guard fails, LKSU reports a blocked reboot rather than forcing one. A system that never boots cannot send mail or recover automatically: confirm your provider console and an external snapshot **once before enabling unattended reboot**, and test on a nonproduction VM first.

**Generic health-check setup:** During `lksu configure` or `lksu configure-automation`, the program suggests currently running boot-enabled application services. Press Enter to accept, type a custom comma-separated set (e.g. `nginx,postgresql` or `my-app`), or use HTTP(S) health URLs (enter `none` for service checks only when health URLs are configured). An inactive or absent app service cannot be treated as a passing check. LKSU deliberately does not treat operating-system infrastructure such as SSH, DBus or the LKSU unit itself as proof that the application works.

## Event-only email notifications (v0.3.17)

LKSU's unchanged read-only checks are silent: no email for successful scans, no available RPM upgrades, no self-update available, or unchanged releases. Notifications are event based: actual kernel installation, staged transition, post-boot verification success/failure, successful application update or attempted operation failure. Repeat events are deduplicated; SMTP failures are not marked delivered.

The first-install wizard asks `Email only when updates succeed or fail?`, default **yes**, and offers guarded automatic reboot by default. It still requires explicit recovery readiness and passing real service/HTTP checks before first automatic reboot. After one-time configuration, **no manual SSH reboot command** is needed during normal eligible updates. Existing installations retain their automation settings, which can be adjusted once using `sudo lksu configure-automation` without re-entering SMTP credentials. LKSU cannot manufacture a provider snapshot or prove remote-console access.

## Email reports

LKSU notification emails are written in English, with a readable subject and plain-text report. They include the hostname, report time, running/installed kernels, update/advisory counts, install policy, continuous 15-minute kernel check cadence, and recorded fallback kernel status. Unknown counts show **Not checked**; the actual next systemd timer firing is not guessed.

The `lksu-maintenance.timer` runs every 15 minutes regardless of hour. With automatic installation disabled, the maintenance command is read-only; with installation enabled, it can install and (if separately authorized and safe) reboot. Routine checks send no email; repeated errors are deduplicated. The daily `scheduled` check stays read-only and reports to fleet; failed attempted updates trigger an English event email.

The preserved previous kernel is **not** a full system backup. Mail never claims successful rollback without proving it.

## Manual operations

`sudo lksu initialize` runs the first-install kernel update procedure (possibly causing a guarded reboot). For read-only checks use `sudo lksu scheduled`.


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

The interactive setup requests a report address, SMTP host/port, username, password or app password, policy, and health-check service names. Configuration is written to `/etc/lksu/config.json` as mode 0600. Use a dedicated SMTP credential. Port 465 uses implicit TLS; other ports require STARTTLS and certificate verification. Avoid shared administrator account credentials. **Read the [beginner SMTP setup guide](#beginners-email-setup-postmark-smtp2go-or-your-own-smtp) above.** The read-only `sudo lksu scheduled` command does not send test email; validate account approval, verified sender, TLS connectivity and actual event delivery separately.

To change installation and reboot without modifying SMTP credentials, run `sudo lksu configure-automation`. It configures the install policy, update/reboot opt-ins, recovery approval and application health checks; the 15-minute timer remains active with **no time-window restriction**. Kernel transactions use enabled DNF repositories only. Guarded reboot occurs automatically for eligible changes only when preflight succeeds. A preserved kernel is not a system snapshot.

## Exceptional manual recovery / troubleshooting (not the normal automatic workflow)

```bash
sudo lksu check
sudo lksu apply                 # requires security-only or all-stable policy
sudo cat /var/lib/lksu/state.json
sudo lksu stage-reboot          # preserves old default, stages new kernel once
# Confirm provider snapshot and console access, then reboot in an approved window.
sudo reboot
sudo lksu verify
uname -r
systemctl is-active <your-application-service>
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

`install.sh` installs systemd unit files and enables LKSU self-updates. The interactive bootstrap enables the daily read-only timer, 15-minute kernel timer and boot verifier; install/reboot authorization and recovery prerequisites remain separate. `packaging/lksu.spec` is an RPM packaging preview, not a signed release.

When `automatic_reboot` is enabled, LKSU stages a one-shot trial and requests the system reboot in the same eligible maintenance run after update/adoption, provided that the one-time recovery approval, active health checks and post-boot verification unit pass. The interactive setup **offers** automatic reboot by default, but without verified recovery readiness it is safely blocked. `lksu scheduled` remains read-only.

For any host, run `sudo lksu scheduled` (read-only) to see the installed and running kernel and whether a reboot is pending. Do not assume every server runs the same hosting panel or services.
