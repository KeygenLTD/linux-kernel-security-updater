# Email notifications and SMTP configuration

LKSU uses SMTP to deliver operational reports. The installer asks for the recipient email, SMTP provider, authentication details, update preferences and health checks.

> [!IMPORTANT]
> This page documents the **current main-branch implementation**. Development-branch features may differ. Never post SMTP credentials or the complete configuration file in a public issue.

## Initial configuration

Run `sudo lksu configure` after reviewing the installation process. The setup supports:

| Provider | SMTP host | Port | Credentials |
| --- | --- | --- | --- |
| Postmark | `smtp.postmarkapp.com` | 587 | Postmark Server Token used as username and password |
| SMTP2GO | `mail.smtp2go.com` | 587 | SMTP2GO SMTP username and password |
| Custom | Supplied by your mail provider | 465 by default (or provider-specified port) | SMTP username and password/app password |

The recipient address is entered as **Report email**. In the current setup, `from_email` defaults to the same address. Many providers require a verified sender/domain; configure a provider-authorized sender before relying on delivery.

## Configuration keys

LKSU stores its configuration at `/etc/lksu/config.json`. These are **top-level** keys, not a nested `smtp` object:

| Key | Purpose |
| --- | --- |
| `email` | Recipient address |
| `from_email` | Sender address |
| `smtp_host` | SMTP server |
| `smtp_port` | SMTP port |
| `smtp_user` | SMTP login |
| `smtp_password` | SMTP password or token |
| `notifications` | Whether event emails are enabled |

Do **not** paste real values into issues, logs or screenshots. Restrict configuration access to root (`chmod 600 /etc/lksu/config.json`). Back up credentials securely.

## TLS behavior

The current code uses **implicit TLS** for port **465** (`SMTP_SSL`). For other configured ports it connects using SMTP and then requires **STARTTLS**, before authenticating and sending. The implementation does not provide an unencrypted SMTP fallback.

## When are messages sent?

The setup offers the preference **“Email only when updates succeed or fail?”**. Notification behavior also depends on the operation and its reporting path. Do not assume that a 15-minute read-only check produces an email; inspect actual notification results and logs when validating delivery.

## Troubleshooting

<details>
<summary>Authentication failed</summary>

Check the SMTP username/token, provider account status, and whether the provider requires an application password or verified sender. Do not share secrets in a public issue.

</details>

<details>
<summary>Connection timed out or TLS failed</summary>

Check outbound firewall/network rules, DNS resolution, the configured port, and whether the provider supports implicit TLS (465) or STARTTLS (typically 587). Do not disable certificate verification to make delivery work.

</details>

<details>
<summary>SMTP accepted the message but no email arrived</summary>

Inspect provider delivery/activity logs, sender verification, recipient spam folder and SPF/DKIM/DMARC records for your sending domain. SMTP acceptance is not proof of inbox delivery.

</details>

<details>
<summary>Can I update SMTP settings without reinstalling?</summary>

The current main-branch CLI does not expose a dedicated SMTP reconfiguration command. Make a secure backup, edit the root-only configuration carefully, and verify JSON syntax and permissions. Do not use `configure` casually on an active host because it also asks for kernel automation preferences.

</details>

## Safe verification

Check the JSON syntax without printing secrets:

```bash
sudo python3 -m json.tool /etc/lksu/config.json >/dev/null
sudo stat -c '%a %U:%G' /etc/lksu/config.json
```

A successful syntax check does not test SMTP connectivity or actual inbox delivery. For an end-to-end test, use an explicitly authorized operational event and inspect provider delivery records; do not trigger a production kernel update solely to test email.
