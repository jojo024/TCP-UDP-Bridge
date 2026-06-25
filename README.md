# TCP-UDP Bridge

A small Python toolkit for working with **TSL UMD v5.0** tally data. It accepts
TSL v5 messages over **TCP**, decodes them, and forwards them on to a downstream
service (e.g. [Cerebrum](https://www.axon.tv/)) over **UDP**.

TSL v5 over TCP wraps every packet in a `FE 02` (DLE/STX) framing header so a
receiver can re-synchronise to packet boundaries on a byte stream. The UDP form
of the protocol does not use this wrapper. This bridge handles the conversion:
it reassembles the TCP stream, strips the `FE 02` header, and emits a clean UDP
payload.

## Contents

| File | Purpose |
|------|---------|
| `TallyBridge.py`   | TCP → UDP bridge. Listens for TSL v5 TCP, decodes, and forwards as UDP. |
| `TallyListener.py` | Standalone diagnostic listener. Accepts a single TSL v5 TCP connection and pretty-prints each packet. |

## Requirements

- Python 3.8+ (standard library only — no external dependencies)

## Usage

### Bridge (TCP → UDP)

Edit the configuration constants at the top of `TallyBridge.py`:

```python
TCP_BIND_IP   = '0.0.0.0'        # interface to listen on
TCP_BIND_PORT = 9000             # port your TSL source connects to
CEREBRUM_IP   = '10.40.41.10'    # downstream UDP destination
CEREBRUM_PORT = 9000
```

Then run:

```bash
python TallyBridge.py
```

Each complete packet received is logged (raw hex + decoded summary) and forwarded
to the configured UDP destination.

To run it persistently on a Linux host (systemd service, firewall, logs), see
[DEPLOY.md](DEPLOY.md).

### Listener (diagnostic)

```bash
python TallyListener.py
```

You will be prompted for an IP/port to bind to. Useful for confirming a source
device is emitting valid TSL v5 TCP before putting the bridge in line.

## How it works

1. **Stream reassembly** — incoming TCP bytes are buffered. The bridge locates
   each `FE 02` marker and reads the 2-byte little-endian `PBC` (packet byte
   count) to determine the exact end of each packet, so fragmented or
   back-to-back packets are handled correctly.
2. **Unwrap** — the `FE 02` framing bytes are stripped, leaving the
   UDP-compatible payload (starting at the PBC field).
3. **Decode** — version, screen index, display index, the three tally states
   (RH / Text / LH), and the UMD text are parsed for logging.
4. **Forward** — the unwrapped payload is sent verbatim over UDP.

## TSL v5 packet layout (after `FE 02`)

| Offset | Size | Field |
|--------|------|-------|
| 0 | 2 | PBC (packet byte count, LE) |
| 2 | 1 | Version |
| 3 | 1 | Flags |
| 4 | 2 | Screen index (LE) |
| 6 | 2 | Display index (LE) |
| 8 | 2 | Control data (tally bits, LE) |
| 10 | 2 | Text length (LE) |
| 12 | n | UMD text (ASCII) |

Tally states are packed into the control byte: bits 0–1 = RH tally,
bits 2–3 = Text tally, bits 4–5 = LH tally (`0=off, 1=red, 2=green, 3=amber`).

## License

MIT — see [LICENSE](LICENSE).
