# Security Policy

LKSU is an early release that changes boot-critical packages. Test it on a disposable AlmaLinux VM and perform a provider-console recovery drill before production use.

Do not include SMTP credentials, server addresses, logs containing private data, or other secrets in public issues. Report suspected vulnerabilities privately through GitHub's **Security advisories** page for this repository. Include the affected version, AlmaLinux major version, architecture, boot mode, a minimal reproduction, and the security impact.

Security fixes are provided on a best-effort basis. No version is currently designated as a long-term supported release.


## Additional resources

- [CVE reporting and patch verification](docs/cve-security.md)
- [Recovery playbook](docs/recovery.md)
- [Platform support matrix](docs/platform-support.md)

> [!CAUTION]
> A reported CVE does not prove a host is vulnerable or protected. Confirm the vendor patch, running kernel and post-boot verification.
