#!/usr/bin/env python3
"""
sigutil.py - make SIGTERM behave like Ctrl-C.

Python raises KeyboardInterrupt for SIGINT but silently dies on SIGTERM, so
`timeout`, `kill`, and run.sh's cleanup would bypass our try/finally blocks
and leak the CAN socket. Converting SIGTERM into KeyboardInterrupt means one
cleanup path covers every way these programs get stopped.
"""
import signal

__all__ = ["install"]


def _raise_interrupt(signum, frame):
    raise KeyboardInterrupt()


def install():
    for sig in (signal.SIGTERM, signal.SIGHUP):
        try:
            signal.signal(sig, _raise_interrupt)
        except (ValueError, OSError, AttributeError):
            pass   # not on main thread, or signal missing on this platform

    # A parent shell can hand us SIGINT set to SIG_IGN (bash does this for
    # non-interactive background jobs). Reclaim it so Ctrl-C always works.
    try:
        if signal.getsignal(signal.SIGINT) == signal.SIG_IGN:
            signal.signal(signal.SIGINT, _raise_interrupt)
    except (ValueError, OSError, AttributeError):
        pass
