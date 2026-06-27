#!/usr/bin/env python3
"""
TSL v5 UDP tester — send crafted tally packets to Cerebrum (or any TSL v5 UDP
receiver) to verify connectivity, and optionally listen for packets to confirm
they arrive on the wire.

Examples:
  # One packet: display index 1, left-hand tally RED, text "TEST"
  python3 TallyUDPTester.py --ip 192.168.240.11 --port 9000 --index 1 --lh red --text TEST

  # Cycle through tally states every 2s so you can watch Cerebrum react
  python3 TallyUDPTester.py --ip 192.168.240.11 --index 1 --cycle --interval 2

  # Listen mode: bind locally and decode any TSL v5 UDP that arrives
  python3 TallyUDPTester.py --listen --port 9000
"""

import argparse
import socket
import sys
import time
from datetime import datetime

# ---- Defaults (override with CLI flags) ----
DEFAULT_IP   = '192.168.240.11'   # Cerebrum UDP destination
DEFAULT_PORT = 9000

TALLY_NAMES = {'off': 0, 'red': 1, 'green': 2, 'amber': 3}
TALLY_LABELS = {0: 'OFF', 1: 'RED', 2: 'GREEN', 3: 'AMBER'}


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def parse_tally(value: str) -> int:
    """Accept a tally state as a name (off/red/green/amber) or 0-3."""
    v = value.strip().lower()
    if v in TALLY_NAMES:
        return TALLY_NAMES[v]
    if v.isdigit() and 0 <= int(v) <= 3:
        return int(v)
    raise argparse.ArgumentTypeError(
        f"invalid tally '{value}' (use off/red/green/amber or 0-3)")


def build_tsl5_udp(screen: int, index: int, rh: int, text_tally: int,
                   lh: int, brightness: int, text: str) -> bytes:
    """Build a TSL UMD v5.0 UDP packet (no FE 02 wrapper — UDP form).

    Layout: PBC(2) VER(1) FLAGS(1) SCREEN(2) INDEX(2) CONTROL(2) LEN(2) TEXT(n)
    All multi-byte fields little-endian. PBC counts every byte after itself.
    """
    text_bytes = text.encode('ascii', errors='ignore')

    # Control word: bits 0-1 RH, 2-3 text, 4-5 LH, 6-7 brightness, bit15=0 (display data)
    control = ((rh & 0x03)
               | ((text_tally & 0x03) << 2)
               | ((lh & 0x03) << 4)
               | ((brightness & 0x03) << 6))

    body = bytearray()
    body += bytes([0x00])                              # VER
    body += bytes([0x00])                              # FLAGS
    body += screen.to_bytes(2, 'little')               # SCREEN
    body += index.to_bytes(2, 'little')                # display INDEX
    body += control.to_bytes(2, 'little')              # CONTROL
    body += len(text_bytes).to_bytes(2, 'little')      # text LENGTH
    body += text_bytes                                 # TEXT

    pbc = len(body).to_bytes(2, 'little')              # bytes following PBC
    return bytes(pbc) + bytes(body)


def send_one(sock: socket.socket, dest: tuple, screen: int, index: int,
             rh: int, text_tally: int, lh: int, brightness: int, text: str) -> None:
    pkt = build_tsl5_udp(screen, index, rh, text_tally, lh, brightness, text)
    sock.sendto(pkt, dest)
    print(f"[{ts()}] SENT {len(pkt)}B -> {dest[0]}:{dest[1]}  "
          f"Screen={screen} Index={index} | "
          f"RH={TALLY_LABELS[rh]} Text={TALLY_LABELS[text_tally]} LH={TALLY_LABELS[lh]} "
          f"Bright={brightness} | \"{text}\"")
    print(f"          HEX : {pkt.hex(' ').upper()}")


def run_sender(args) -> None:
    dest = (args.ip, args.port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"TSL v5 UDP tester -> {dest[0]}:{dest[1]}")

    try:
        if args.cycle:
            # Visually distinct states so it's obvious on the Cerebrum display
            sequence = [
                (0, 0, 0, "OFF"),
                (1, 0, 0, "RH RED"),
                (0, 2, 0, "TEXT GREEN"),
                (0, 0, 3, "LH AMBER"),
            ]
            print(f"Cycling {len(sequence)} states every {args.interval}s. Ctrl+C to stop.\n")
            i = 0
            while True:
                rh, txt, lh, label = sequence[i % len(sequence)]
                send_one(sock, dest, args.screen, args.index, rh, txt, lh,
                         args.brightness, label)
                i += 1
                time.sleep(args.interval)
        else:
            for n in range(args.count):
                send_one(sock, dest, args.screen, args.index, args.rh,
                         args.text_tally, args.lh, args.brightness, args.text)
                if n + 1 < args.count:
                    time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        sock.close()


def run_listener(args) -> None:
    bind_ip = args.bind
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((bind_ip, args.port))
    print(f"Listening for TSL v5 UDP on {bind_ip}:{args.port}. Ctrl+C to stop.\n")
    try:
        while True:
            data, src = sock.recvfrom(2048)
            print(f"[{ts()}] RECV {len(data)}B from {src[0]}:{src[1]}")
            print(f"          HEX : {data.hex(' ').upper()}")
            decode(data)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        sock.close()


def decode(payload: bytes) -> None:
    """Decode and print a received TSL v5 UDP payload."""
    if len(payload) < 12:
        print(f"          [WARN] too short to decode ({len(payload)}B)")
        return
    pbc = int.from_bytes(payload[0:2], 'little')
    version = payload[2]
    screen = int.from_bytes(payload[4:6], 'little')
    index = int.from_bytes(payload[6:8], 'little')
    tally = payload[8]
    rh, txt, lh = tally & 0x03, (tally >> 2) & 0x03, (tally >> 4) & 0x03
    tlen = int.from_bytes(payload[10:12], 'little')
    text = payload[12:12 + tlen].decode('ascii', errors='ignore') if tlen else ""
    note = "" if pbc == len(payload) - 2 else f"  (!) PBC={pbc} but {len(payload) - 2}B follow"
    print(f"          v{version} | Screen={screen} Index={index} | "
          f"RH={TALLY_LABELS[rh]} Text={TALLY_LABELS[txt]} LH={TALLY_LABELS[lh]} | "
          f"\"{text}\"{note}")


def main() -> None:
    p = argparse.ArgumentParser(description="TSL v5 UDP tester for Cerebrum")
    p.add_argument('--ip', default=DEFAULT_IP, help=f"destination IP (default {DEFAULT_IP})")
    p.add_argument('--port', type=int, default=DEFAULT_PORT, help=f"UDP port (default {DEFAULT_PORT})")
    p.add_argument('--screen', type=int, default=0, help="screen index (default 0)")
    p.add_argument('--index', type=int, default=0, help="display index / address (default 0)")
    p.add_argument('--rh', type=parse_tally, default=0, help="right-hand tally: off/red/green/amber")
    p.add_argument('--text-tally', type=parse_tally, default=0, help="text tally: off/red/green/amber")
    p.add_argument('--lh', type=parse_tally, default=0, help="left-hand tally: off/red/green/amber")
    p.add_argument('--brightness', type=int, default=3, choices=range(0, 4), help="0-3 (default 3)")
    p.add_argument('--text', default='TEST', help="UMD text (default 'TEST')")
    p.add_argument('--count', type=int, default=1, help="how many packets to send (default 1)")
    p.add_argument('--interval', type=float, default=1.0, help="seconds between packets (default 1.0)")
    p.add_argument('--cycle', action='store_true', help="loop through tally states until Ctrl+C")
    p.add_argument('--listen', action='store_true', help="listen/decode incoming UDP instead of sending")
    p.add_argument('--bind', default='0.0.0.0', help="listen bind address (default 0.0.0.0)")
    args = p.parse_args()

    if args.listen:
        run_listener(args)
    else:
        run_sender(args)


if __name__ == '__main__':
    sys.exit(main())
