import socket
import threading
from datetime import datetime

# ---- Configuration ----
TCP_BIND_IP   = '192.168.240.12'
TCP_BIND_PORT = 9000         # Port to accept TSL v5 TCP connections on

CEREBRUM_IP   = '192.168.240.11'
CEREBRUM_PORT = 9000         # Cerebrum UDP destination port

# ---- TSL v5 TCP framing bytes ----
TSL_DLE = 0xFE
TSL_STX = 0x02

_udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Serialises log output across client threads so multi-line records stay intact
_log_lock = threading.Lock()


def log(msg: str = "", *, detail: bool = False) -> None:
    """Print a timestamped log line.

    detail=True indents the line and omits the timestamp, so it reads as
    continuation detail beneath the preceding timestamped event.
    """
    with _log_lock:
        if detail:
            print(f"    {msg}")
        elif msg:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{ts}] {msg}")
        else:
            print()


def parse_tsl_v5(payload: bytes) -> None:
    """Print a decoded summary of a TSL v5 payload (FE 02 already stripped)."""
    if len(payload) < 12:
        log(f"[WARN] Payload too short to parse ({len(payload)} bytes)")
        return

    version       = payload[2]
    screen_index  = int.from_bytes(payload[4:6],  byteorder='little')
    display_index = int.from_bytes(payload[6:8],  byteorder='little')
    text_length   = int.from_bytes(payload[10:12], byteorder='little')

    tally_byte = payload[8]
    rh  = tally_byte & 0x03
    txt = (tally_byte >> 2) & 0x03
    lh  = (tally_byte >> 4) & 0x03

    tally_labels = {0: "OFF", 1: "RED", 2: "GREEN", 3: "AMBER"}
    label = ""
    if text_length > 0 and len(payload) >= 12 + text_length:
        label = payload[12:12 + text_length].decode('ascii', errors='ignore')

    log(f"v{version} | Screen={screen_index} Display={display_index} | "
        f"RH={tally_labels[rh]} Text={tally_labels[txt]} LH={tally_labels[lh]} | \"{label}\"",
        detail=True)


def extract_packets(buf: bytes):
    """Parse complete TSL v5 TCP packets out of a stream buffer.

    TSL v5 TCP wraps every packet with FE 02 (DLE/STX) followed by
    PBC (2-byte LE) that counts all subsequent bytes in the packet body.
    Strips the FE 02 wrapper and returns (list_of_payloads, remaining_buf).
    """
    packets = []
    while True:
        idx = buf.find(bytes([TSL_DLE, TSL_STX]))
        if idx == -1:
            buf = b''
            break
        if idx > 0:
            log(f"[WARN] Skipping {idx} unrecognised bytes before packet marker")
            buf = buf[idx:]
        if len(buf) < 4:
            break  # need FE 02 + 2 PBC bytes before we know total length
        pbc = int.from_bytes(buf[2:4], byteorder='little')
        total = 2 + pbc  # FE(1) + STX(1) + PBC-counted body
        if len(buf) < total:
            break  # incomplete packet — wait for more data
        payload = buf[2:total]  # everything after FE 02 (UDP-ready)
        packets.append(payload)
        buf = buf[total:]
    return packets, buf


def handle_client(conn: socket.socket, addr: tuple) -> None:
    log(f"[CONNECT]    {addr[0]}:{addr[1]}")
    buf = b''
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
            packets, buf = extract_packets(buf)
            for payload in packets:
                log(f"[FORWARD] {len(payload)}B  {addr[0]} → UDP {CEREBRUM_IP}:{CEREBRUM_PORT}")
                log(f"RAW : {payload.hex(' ').upper()}", detail=True)
                parse_tsl_v5(payload)
                _udp_sock.sendto(payload, (CEREBRUM_IP, CEREBRUM_PORT))
    except OSError as e:
        log(f"[ERROR] {addr}: {e}")
    finally:
        conn.close()
        log(f"[DISCONNECT] {addr[0]}:{addr[1]}")


def start_bridge() -> None:
    print("=" * 55)
    print("  TSL v5  TCP → UDP  Bridge")
    print(f"  Listening  TCP : {TCP_BIND_IP}:{TCP_BIND_PORT}")
    print(f"  Forwarding UDP : {CEREBRUM_IP}:{CEREBRUM_PORT}")
    print("=" * 55)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((TCP_BIND_IP, TCP_BIND_PORT))
    server.listen(5)
    log("Waiting for connections... (Ctrl+C to stop)")

    try:
        while True:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        log("[STOP] Bridge shutting down.")
    finally:
        server.close()
        _udp_sock.close()


if __name__ == '__main__':
    start_bridge()
