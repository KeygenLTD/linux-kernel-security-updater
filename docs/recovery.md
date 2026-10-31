# Recovery playbook

> [!CAUTION]
> Have an external snapshot and provider console access before enabling unattended reboot. A fallback kernel is not a substitute for a verified backup.

## Before updating

1. Verify provider-console access and a recent external snapshot.
2. Confirm working service or HTTP health checks.
3. Review `lksu active`, `lksu check --json`, and `lksu kernel-inventory --json`.
4. Confirm the running and fallback kernels are installed and bootable.

## If the new kernel does not boot

1. Open the provider console and inspect the boot menu.
2. Choose the previous known-working kernel if available.
3. Inspect journal logs, GRUB entries and storage before retrying.
4. Do not erase the running or fallback kernel.

## If the server boots but health checks fail

1. Check `lksu active` and service status.
2. Inspect `journalctl -u lksu-verify.service` and application logs.
3. When rollback is appropriate, use `sudo lksu select-old`, confirm `grubby --default-kernel`, and reboot only with console recovery available.

Do not recreate an integrity baseline or bypass health gates until unexpected changes have been investigated.
