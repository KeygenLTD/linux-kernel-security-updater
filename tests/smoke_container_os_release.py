"""Real container metadata smoke; not an installed/booted kernel test."""
import sys
from pathlib import Path
from lksu.distributions import detect, require_automatic_kernel_backend
from lksu.core import LKSUError

distro = detect(Path(sys.argv[1]))
assert distro.identifier == sys.argv[2], (distro.identifier, sys.argv[2])
assert distro.update_capability != "enabled"
assert distro.reboot_capability == "blocked"
try:
    require_automatic_kernel_backend(distro)
except LKSUError:
    pass
else:
    raise AssertionError("Unsafe kernel automation permitted")
print("PASS", distro.identifier, distro.family, distro.package_manager, "automation blocked")
