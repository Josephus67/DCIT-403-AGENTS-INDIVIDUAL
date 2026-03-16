# Smart Campus Energy Monitor
### DCIT 403 — Individual Intelligent Agent Project
### Prometheus Methodology | SPADE + jabber.hot-chilli.net

---

## Overview

A multi-agent system that monitors university campus energy consumption,
automatically reduces power in unoccupied rooms, detects anomalous activity,
and notifies facilities/security staff in real time.

**Three agents:**
| Agent | JID | Role |
|-------|-----|------|
| MonitorAgent | monitor@jabber.hot-chilli.net | Perceives environment (sensors, schedules) |
| DecisionAgent | decision@jabber.hot-chilli.net | Reasons and acts (device commands, load shedding) |
| AlertAgent | alert@jabber.hot-chilli.net | Logs events, notifies staff, tracks faults |

---

## Prerequisites

- Python 3.9 or higher
- pip
- Optional: Docker (if running a local Prosody XMPP server)

You can run this project with either:
- Public XMPP accounts (jabber.hot-chilli.net)
- A local Prosody server in Docker (recommended for offline/local testing)

---

## Option B — Local XMPP with Prosody (Docker)

If you prefer local testing, start a Prosody container and register the three agent users.

### 1) Start Prosody in Docker

```bash
docker run -d \
  --name prosody \
  -p 5222:5222 \
  -p 5269:5269 \
  prosody/prosody:latest
```

If the container already exists, start it with:

```bash
docker start prosody
```

### 2) Register agent accounts inside Prosody

```bash
docker exec prosody prosodyctl register cem_monitor localhost 123
docker exec prosody prosodyctl register cem_decision localhost 123
docker exec prosody prosodyctl register cem_alert localhost 123
```

These match the default credentials in `main.py`:
- `cem_monitor@localhost` / `123`
- `cem_decision@localhost` / `123`
- `cem_alert@localhost` / `123`

### 3) Run the simulation

```bash
python main.py
```

No extra credential flags are needed when using the defaults above.

---

## Step 1 — Register three jabber.hot-chilli.net accounts

Go to **https://www.jabber.hot-chilli.net** and register three separate accounts:

| Account purpose | Suggested username |
|----------------|-------------------|
| MonitorAgent   | monitor       |
| DecisionAgent  | decision      |
| AlertAgent     | alert         |

Each will get a JID like `monitor@jabber.hot-chilli.net`.

> **Note:** jabber.hot-chilli.net is a free public XMPP server. Accounts may require
> email verification. Use different passwords for each account.

---

## Step 2 — Clone / extract the project

```bash
cd ~
# If using a zip:
unzip campus_energy_monitor.zip
cd campus_energy_monitor
```

---

## Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

Verify SPADE is installed:
```bash
python -c "import spade; print(spade.__version__)"
```
Expected: `3.3.x` or higher.

---

## Step 4 — Configure credentials

Open `main.py` and update the `DEFAULT_CREDS` dictionary at the top:

```python
DEFAULT_CREDS = {
    "monitor":  {"jid": "monitor@jabber.hot-chilli.net",  "pwd": "123456"},
    "decision": {"jid": "decision@jabber.hot-chilli.net", "pwd": "123456"},
    "alert":    {"jid": "alert@jabber.hot-chilli.net",    "pwd": "123456"},
}
```

Replace `YOUR_*_PASSWORD` with the passwords you chose during registration.

The passwords have been set as follows:
- MonitorAgent: 123456
- DecisionAgent: 1234567
- AlertAgent: 1234567

Alternatively, pass credentials as command-line arguments (see Step 5).

---

## Step 5 — Run the simulation

### Default run (2 real minutes = ~2 simulated hours):
```bash
python main.py
```

### Custom duration (e.g. 5 real minutes):
```bash
python main.py --duration 300
```

### Run indefinitely (Ctrl+C to stop):
```bash
python main.py --duration 0
```

### Pass credentials on the command line:
```bash
python main.py \
  --monitor-jid  monitor@jabber.hot-chilli.net  --monitor-pwd  123456 \
  --decision-jid decision@jabber.hot-chilli.net --decision-pwd 123456 \
  --alert-jid    alert@jabber.hot-chilli.net    --alert-pwd    123456
```

---

## Project Structure

```
campus_energy_monitor/
│
├── main.py                        # Entry point — starts all agents
├── requirements.txt
├── energy_monitor.log             # Generated on first run
│
├── simulation/
│   └── environment.py             # Simulated campus (sensors, devices, schedule)
│
├── agents/
│   ├── monitor_agent.py           # MonitorAgent — perceive
│   ├── decision_agent.py          # DecisionAgent — decide + act
│   └── alert_agent.py             # AlertAgent — notify + log
│
└── utils/
    ├── messages.py                # Message type definitions and constructors
    └── logger.py                  # Structured logging to stdout and file
```

---

## What to Expect During a Run

```
============================================================
  Smart Campus Energy Monitor
  DCIT 403 — Intelligent Agent System (Prometheus)
============================================================

[System] Initialising simulated environment...
[AlertAgent]    Online as alert@jabber.hot-chilli.net
[DecisionAgent] Online as decision@jabber.hot-chilli.net
[MonitorAgent]  Online as monitor@jabber.hot-chilli.net

[System] All agents running. Simulation in progress...

[MonitorAgent]  Polled 6 rooms | Sim time: Monday 08:05

[DecisionAgent] Evaluating LH-1 | Occupied: False | Schedule: idle | Time: Monday 08:05
[DecisionAgent]  → Plan P1: Reducing devices in LH-1
[DecisionAgent]   ✓ LH-1/lights → dim
[DecisionAgent]   ✓ LH-1/AC → eco
[DecisionAgent]   ✓ LH-1/projector → off

09:00:01  INFO      📋  [LOG] LH-1: Device command executed: lights → dim
09:00:01  INFO      📋  [LOG] LH-1: Device command executed: AC → eco

[DecisionAgent] Evaluating LH-1 | Occupied: True | Schedule: active | Time: Monday 09:10
[DecisionAgent]  → Plan P2: Restoring devices in LH-1
[DecisionAgent]   ✓ LH-1/lights → on
[DecisionAgent]   ✓ LH-1/AC → on

[DecisionAgent] 🔋 PEAK HOUR — activating load shedding (Monday 12:00)
...
09:01:30  WARNING   🚨  [SECURITY] LAB-B: Occupancy detected outside scheduled hours at Saturday 23:00
09:01:30  INFO      📣  [NOTIFY → Security Desk]: [ANOMALY] LAB-B at Saturday 23:00: ...
```

---

## Mapping to Prometheus Design

| Prometheus Artifact | Implementation |
|---------------------|----------------|
| Goals G1.1, G2.1 | `PeriodicSensorBehaviour` in MonitorAgent |
| Goals G1.2, G2.2 | `ReceiveStateBehaviour` in DecisionAgent (Plans P1, P2) |
| Goal G1.3 | `PeakHourBehaviour` in DecisionAgent (Plan P4) |
| Goals G3.2, G3.3 | `ReceiveAlertBehaviour` in AlertAgent |
| Plan P3 (retry) | `_command_device()` in DecisionAgent |
| ROOM_STATE_UPDATE | `utils/messages.py` → `make_room_state_update()` |
| ANOMALY_FLAG | `utils/messages.py` → `make_anomaly_flag()` |
| ALERT_REQUEST | `utils/messages.py` → `make_alert_request()` |
| Acquaintance diagram | MonitorAgent ↔ DecisionAgent ↔ AlertAgent via XMPP ACL |
| Environment percepts | `simulation/environment.py` → `get_room_state()` |
| Environment actions | `simulation/environment.py` → `send_device_command()` |
| Fault registry belief | `AlertAgent.fault_registry` dict |
| Pending retries belief | `DecisionAgent.pending_retries` dict |

---

## Troubleshooting

**"Authentication failed" on startup**
→ Double-check your JID and password in `main.py`.
→ Ensure the jabber.hot-chilli.net account was successfully verified/activated.
→ Try logging in with a desktop XMPP client (e.g. Gajim) to confirm credentials.

**"Connection refused" or timeout**
→ Check your internet connection.
→ jabber.hot-chilli.net may be temporarily down — retry after a few minutes.

**Agents start but no messages are exchanged**
→ Ensure all three JIDs are on the same server (all @xmpp.jp).
→ SPADE requires the recipient JID to be available before sending. The startup
   delay (`asyncio.sleep`) in main.py handles this — if issues persist, increase it.

**ModuleNotFoundError: spade**
→ Run `pip install spade` or `pip install -r requirements.txt` again.
→ Confirm you are using the correct Python environment.

---

## Simulated Time

The environment runs at **60× real time** (1 real second = 1 simulated minute).
A 2-minute real run covers approximately 2 simulated hours.

You can change this by editing `_time_speed` in `simulation/environment.py`.

---

*DCIT 403 Semester Project — Prometheus Methodology*
*Platform: Python 3.9+ | SPADE 3.3+ | XMPP server: xmpp.jp*
