"""Operator progress events for interactive SSH sessions and systemd journals.

Events go to stderr so --json stdout remains machine-readable. They are
best-effort and never decide whether an update/reboot is safe.
"""
import sys


def event(phase, message):
    try:
        print(f"LKSU [{phase}] {message}", file=sys.stderr, flush=True)
    except OSError:
        # A disconnected terminal must not change kernel/reboot decisions.
        pass
