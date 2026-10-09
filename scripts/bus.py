#!/usr/bin/env python3
"""
bus.py - open a CAN bus, with a root-free fallback.

  vcan0 / can0 ...   -> socketcan (realistic, needs `sudo ./setup_vcan.sh`)
  udp                -> udp_multicast, works with NO root at all, and still
                        spans separate processes so sim/dash/attacks behave
                        the same way. candump will NOT see this bus.
"""
import can

UDP_GROUP = "224.0.0.251"
UDP_PORT = 43113


def open_bus(iface, receive_own=False):
    if iface in ("udp", "udpmc", "nosudo"):
        try:
            import msgpack  # noqa: F401
        except ImportError:
            raise SystemExit(
                "[!] the 'udp' bus needs msgpack:\n"
                "      ./.venv/bin/pip install msgpack\n"
                "    or use socketcan instead: sudo ./setup_vcan.sh && "
                "./run.sh")
        b = can.interface.Bus(
            interface="udp_multicast",
            channel=UDP_GROUP,
            port=UDP_PORT,
            receive_own_messages=receive_own,
        )
        # loopback multicast drops badly with the default socket buffer
        try:
            import socket
            s = b._multicast._socket
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 << 20)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 8 << 20)
        except Exception:
            pass
        return b
    if iface in ("virtual", "mem"):
        return can.interface.Bus(interface="virtual", channel="icsim",
                                 receive_own_messages=receive_own)
    try:
        return can.interface.Bus(channel=iface, interface="socketcan",
                                 receive_own_messages=receive_own)
    except OSError as e:
        raise SystemExit(
            f"[!] cannot open socketcan interface '{iface}': {e}\n"
            f"    create it with:  sudo ./setup_vcan.sh {iface}\n"
            f"    or run without root:  ./run.sh -i udp")


def describe(iface):
    if iface in ("udp", "udpmc", "nosudo"):
        return f"udp_multicast {UDP_GROUP}:{UDP_PORT} (no root; candump blind)"
    if iface in ("virtual", "mem"):
        return "in-process virtual bus"
    return f"socketcan {iface}"
