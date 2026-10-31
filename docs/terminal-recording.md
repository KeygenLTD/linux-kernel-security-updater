# Recording a real LKSU terminal walkthrough

This repository does not ship a fabricated terminal demo. Record actual command output on a disposable, authorized test VM before publishing a video or GIF.

## Safe capture

1. Use a test VM with no customer data and no production credentials.
2. Record a short screen capture of these read-only commands:
   ```bash
   lksu --version
   lksu active
   lksu compatibility --json
   lksu check --json
   ```
3. Confirm the exact commands exist in the installed version and that the VM is a supported environment.
4. Review every captured frame for public IPs, hostnames, email addresses, tokens, SMTP settings, service URLs and customer data.
5. Trim the recording and remove audio if not needed. Do not invent success messages, splice unrelated runs, or present a VM result as a production guarantee.
6. Once reviewed, commit the real recording under `docs/assets/` and link it from both READMEs.

> [!IMPORTANT]
> Do not record automatic installation, kernel reboot or rollback on a production host solely for documentation. A real kernel transition requires snapshot, provider console and health-check safeguards.

A video is intentionally **not linked** until an actual reviewed recording exists.
