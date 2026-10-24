# Contributing

Keep changes small and tied to observable AlmaLinux behavior. Production code must not simulate DNF, GRUB, SMTP, reboot, or health-check success. Mocks belong only in tests.

Before opening a pull request:

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
python3 -m compileall -q src
```

For changes to kernel installation or boot selection, document the AlmaLinux version, architecture, BIOS or UEFI mode, DNF transaction, installed kernel list, default GRUB entry, reboot result, health checks, and console recovery result. Remove hostnames, addresses, credentials, and personal data from evidence.

