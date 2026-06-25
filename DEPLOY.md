# Deploying on Linux

`TallyBridge.py` only uses the Python standard library, so any Linux box with
Python 3.8+ can run it. For a bridge that must stay running, use **systemd**.

## Quick test run

```bash
git clone https://github.com/jojo024/TCP-UDP-Bridge.git
cd TCP-UDP-Bridge
python3 TallyBridge.py
```

Press `Ctrl+C` to stop. Use this to confirm it works before installing the
service.

> **Note on `TCP_BIND_IP`:** the script binds to a specific address
> (e.g. `192.168.240.12`). That IP must exist on one of the Linux machine's
> interfaces or the bind will fail with *"Cannot assign requested address"*.
> Set it to `0.0.0.0` to listen on all interfaces.

## One-command install (recommended)

From the cloned repo directory:

```bash
sudo ./deploy.sh
```

This installs the code to `/opt/tcp-udp-bridge`, creates the `tallybridge`
service account, installs the systemd unit, and enables + starts the service.
Re-run it any time to push code changes and restart. The manual steps below are
equivalent if you prefer to do it by hand.

## Install as a systemd service (manual)

```bash
# 1. Place the code in a stable location
sudo mkdir -p /opt/tcp-udp-bridge
sudo cp TallyBridge.py /opt/tcp-udp-bridge/

# 2. Create an unprivileged service account
sudo useradd -r -s /usr/sbin/nologin tallybridge

# 3. Install the unit file
sudo cp tally-bridge.service /etc/systemd/system/

# 4. Enable + start
sudo systemctl daemon-reload
sudo systemctl enable --now tally-bridge
```

### Managing the service

```bash
sudo systemctl status tally-bridge      # check it's running
sudo systemctl restart tally-bridge     # restart after editing config
journalctl -u tally-bridge -f           # follow live logs (packet output)
```

After changing the config constants in `TallyBridge.py`, copy the file to
`/opt/tcp-udp-bridge/` again and `sudo systemctl restart tally-bridge`.

## Firewall

If a firewall is active, allow the inbound TCP listen port:

```bash
# ufw
sudo ufw allow 9000/tcp

# firewalld
sudo firewall-cmd --permanent --add-port=9000/tcp && sudo firewall-cmd --reload
```

The outbound UDP to Cerebrum normally needs no rule, but confirm egress is
permitted on the destination UDP port if you run a strict egress policy.

## Ports below 1024

Binding `TCP_BIND_PORT` below 1024 as a non-root user fails by default. Either
use a high port (the default 9000 is fine) or grant the capability:

```bash
sudo setcap 'cap_net_bind_service=+ep' /usr/bin/python3
```
