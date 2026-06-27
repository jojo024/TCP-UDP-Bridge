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
| `TallyBridge.py`     | TCP → UDP bridge. Listens for TSL v5 TCP, decodes, and forwards as UDP. |
| `TallyListener.py`   | Standalone diagnostic listener. Accepts a single TSL v5 TCP connection and pretty-prints each packet. |
| `TallyUDPTester.py`  | TSL v5 UDP tester. Sends crafted tally packets to Cerebrum (or any TSL v5 UDP receiver), or listens and decodes incoming UDP. |

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

### UDP tester (verify the path to Cerebrum)

Send tally packets straight to Cerebrum over UDP — no TCP source needed:

```bash
# One packet: display index 1, left-hand tally RED, text "TEST"
python3 TallyUDPTester.py --ip 192.168.240.11 --port 9000 --index 1 --lh red --text TEST

# Cycle through tally states every 2s so you can watch Cerebrum react
python3 TallyUDPTester.py --ip 192.168.240.11 --index 1 --cycle --interval 2

# Listen mode: bind locally and decode any TSL v5 UDP that arrives
python3 TallyUDPTester.py --listen --port 9000
```

Tally states accept `off` / `red` / `green` / `amber` (or `0`-`3`) for the
`--rh`, `--text-tally`, and `--lh` lamps. Run `python3 TallyUDPTester.py -h`
for all options. The packets it emits are byte-identical to what the bridge
forwards, so a successful test confirms Cerebrum and the network path are good.

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
