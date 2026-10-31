# LKSU architecture

```mermaid
flowchart TD
  Timer["15-minute systemd timer"] --> Check["Read-only kernel and vendor advisory checks"]
  Check --> Gate{"Operator enabled updates?"}
  Gate -->|No| Report["Report status"]
  Gate -->|Yes| DNF["Vendor DNF kernel upgrade"]
  DNF --> Health{"Recovery readiness and pre-reboot health checks"}
  Health -->|Blocked| Report
  Health -->|Passed| Trial["One-shot GRUB trial boot"]
  Trial --> Verify{"Post-boot kernel and service verification"}
  Verify -->|Passed| Persist["Confirm new persistent kernel"]
  Verify -->|Failed| Fallback["Preserve previous kernel fallback; operator review"]
```

## Boundaries

- Automatic kernel installation is restricted to supported AlmaLinux backends. See [platform support](platform-support.md).
- The installer uses an isolated Python environment and must not replace CyberPanel or system Python.
- GRUB trial boot is not a guarantee of recovery from disk, bootloader or provider failures.
- Security Watch observes and reports host signals; it does not automatically remediate CVEs.
- No automatic zero-day mitigation engine is implemented.

See [recovery](recovery.md) and [CVE reporting](cve-security.md).
