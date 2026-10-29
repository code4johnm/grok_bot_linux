# async-index heartbeat

`heartbeat.py` is a stdlib script. It pings 1.1.1.1 with ICMP and falls back
to TCP 443. When `GROK_BUS_DIR` (or a known local Grok folder) exists, the same
cycle writes `heartbeat.json` and a `reply-*.yaml` for each new `msg-*.yaml`.

The reply records that the file was seen. It does not run the message. The
desktop agent decides what to execute.

One summary email per UTC day can go through the local `sendmail` to
`jobs4johnm@gmail.com`. The script stores no mail token. If `sendmail` is
absent, it records that mail was not sent.

This script is not `~/.grok/heartbeat.py`. That file pings the LAN gateway for
the Drive watch and stays in place.

## Units

`grok-heartbeat.service` and `grok-heartbeat.timer` are the deposited units.
The timer uses `OnUnitActiveSec=5min`, `OnBootSec=2min`, `Persistent=true`,
and `AccuracySec=30s`. `User=user` matches this machine's login.

Install on the laptop only when the gateway heartbeat must stay untouched:

```bash
sudo mkdir -p /opt/grok
sudo cp async-index/heartbeat.py /opt/grok/heartbeat.py
sudo cp async-index/grok-heartbeat.service async-index/grok-heartbeat.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now grok-heartbeat.timer
```

Those commands are not run by depositing this branch.
