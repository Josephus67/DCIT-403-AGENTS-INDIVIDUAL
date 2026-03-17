# Smart Campus Energy Monitor
### DCIT 403 — Individual Intelligent Agent Project
### Prometheus Methodology | SPADE + Local Prosody (Docker)

---

## Overview

A multi-agent system that monitors university campus energy consumption,
automatically reduces power in unoccupied rooms, detects anomalous activity,
and notifies facilities/security staff in real time.

This project is configured for local-only execution using a Prosody XMPP server
running in Docker.

**Three agents:**
| Agent | JID | Role |
|-------|-----|------|
| MonitorAgent | cem_monitor@localhost | Perceives environment (sensors, schedules) |
| DecisionAgent | cem_decision@localhost | Reasons and acts (device commands, load shedding) |
| AlertAgent | cem_alert@localhost | Logs events, notifies staff, tracks faults |

---

## Prerequisites

- Python 3.9 or higher
- pip
- Docker Desktop (or Docker Engine)

Recommended:
- Use a Python virtual environment for isolation
- Keep ports 5222 and 5269 free on your machine

Preflight checks:

```bash
python --version
pip --version
docker --version
docker info > /dev/null && echo "Docker is running"
```

---

## Quick Start (First Time Setup)

From the project root, run the following in order.

### 1) Create and activate a virtual environment

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2) Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3) Start local XMPP (Prosody) and register agent users

```bash
docker rm -f prosody 2>/dev/null || true
docker run -d --name prosody -p 5222:5222 -p 5269:5269 prosody/prosody:latest
sleep 2
docker exec prosody prosodyctl register cem_monitor localhost 123
docker exec prosody prosodyctl register cem_decision localhost 123
docker exec prosody prosodyctl register cem_alert localhost 123
```

### 4) Run a quick verification

```bash
python main.py --duration 10
```

You should see all three agents connect and authenticate.

---

## Local Setup (Docker Prosody)

### 1) Start Prosody

Create and start the container:

```bash
docker run -d \
  --name prosody \
  -p 5222:5222 \
  -p 5269:5269 \
  prosody/prosody:latest
```

If it already exists:

```bash
docker start prosody
```

### 2) Register local agent accounts

```bash
docker exec prosody prosodyctl register cem_monitor localhost 123
docker exec prosody prosodyctl register cem_decision localhost 123
docker exec prosody prosodyctl register cem_alert localhost 123
```

These match the defaults in `main.py`.

Defaults used by the project:
- Monitor: cem_monitor@localhost / 123
- Decision: cem_decision@localhost / 123
- Alert: cem_alert@localhost / 123

### 3) Install Python dependencies

```bash
pip install -r requirements.txt
```

Optional check:

```bash
python -c "import spade; print(spade.__version__)"
```

### 4) Run the simulation

Default run:

```bash
python main.py
```

Custom duration (seconds):

```bash
python main.py --duration 300
```

Run indefinitely:

```bash
python main.py --duration 0
```

If you changed credentials, pass them via CLI:

```bash
python main.py \
  --monitor-jid  cem_monitor@localhost  --monitor-pwd 123 \
  --decision-jid cem_decision@localhost --decision-pwd 123 \
  --alert-jid    cem_alert@localhost    --alert-pwd 123
```

---

## Success Checklist

After startup, confirm these lines appear:
- Agent cem_alert@localhost connected and authenticated.
- Agent cem_decision@localhost connected and authenticated.
- Agent cem_monitor@localhost connected and authenticated.

Expected behavior during shutdown:
- You may see connection_lost: (None,)
- This is normal when agents stop gracefully

---

## Project Structure

```
campus_energy_monitor/
|
+-- main.py                        # Entry point — starts all agents
+-- requirements.txt
+-- energy_monitor.log             # Generated on first run
|
+-- simulation/
|   +-- environment.py             # Simulated campus (sensors, devices, schedule)
|
+-- agents/
|   +-- monitor_agent.py           # MonitorAgent — perceive
|   +-- decision_agent.py          # DecisionAgent — decide + act
|   +-- alert_agent.py             # AlertAgent — notify + log
|
+-- utils/
    +-- messages.py                # Message type definitions and constructors
    +-- logger.py                  # Structured logging to stdout and file
```

---

## What to Expect During a Run

```text
============================================================
  Smart Campus Energy Monitor
  DCIT 403 — Intelligent Agent System (Prometheus)
============================================================

[System] Initialising simulated environment...
[System] Starting AlertAgent...
[AlertAgent] Online as cem_alert@localhost
[System] Starting DecisionAgent...
[DecisionAgent] Online as cem_decision@localhost
[System] Starting MonitorAgent...
[MonitorAgent] Online as cem_monitor@localhost

[System] All agents running. Simulation in progress...
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
| ROOM_STATE_UPDATE | `utils/messages.py` -> `make_room_state_update()` |
| ANOMALY_FLAG | `utils/messages.py` -> `make_anomaly_flag()` |
| ALERT_REQUEST | `utils/messages.py` -> `make_alert_request()` |
| Acquaintance diagram | MonitorAgent <-> DecisionAgent <-> AlertAgent via XMPP ACL |
| Environment percepts | `simulation/environment.py` -> `get_room_state()` |
| Environment actions | `simulation/environment.py` -> `send_device_command()` |
| Fault registry belief | `AlertAgent.fault_registry` dict |
| Pending retries belief | `DecisionAgent.pending_retries` dict |

---

## Troubleshooting

**"Error during the connection with the server"**
- Check container is running: `docker ps`
- Check XMPP port is listening: `lsof -nP -iTCP:5222 -sTCP:LISTEN`
- Check Prosody logs: `docker logs --tail 80 prosody`
- Verify users exist: `docker exec prosody prosodyctl show user cem_monitor@localhost`
- Ensure your run command uses localhost JIDs, not external domains

**Prosody shows TLS key permission errors**

If logs contain `Failed to load '/etc/prosody/certs/localhost.key'` or
`No stream features to offer`, fix permissions and restart:

```bash
docker exec prosody sh -lc 'chown prosody:prosody /etc/prosody/certs/localhost.key /etc/prosody/certs/localhost.crt && chmod 640 /etc/prosody/certs/localhost.key && chmod 644 /etc/prosody/certs/localhost.crt'
docker restart prosody
```

If problems persist, recreate Prosody completely:

```bash
docker rm -f prosody
docker run -d --name prosody -p 5222:5222 -p 5269:5269 prosody/prosody:latest
sleep 2
docker exec prosody prosodyctl register cem_monitor localhost 123
docker exec prosody prosodyctl register cem_decision localhost 123
docker exec prosody prosodyctl register cem_alert localhost 123
```

**"Authentication failed" on startup**
- Re-register users in Prosody and keep JIDs/passwords aligned with `main.py`.
- Ensure all three accounts are `@localhost`.

**Agents start but no messages are exchanged**
- Start order matters. Keep AlertAgent and DecisionAgent online before MonitorAgent.
- Ensure recipient JIDs are exactly the same domain and usernames.

**ModuleNotFoundError: spade**
- Run `pip install -r requirements.txt` again.
- Confirm you are using the correct Python environment.

**Port already in use (5222/5269)**
- Stop conflicting service, or remove and recreate Prosody with different host ports
- Check port owners: `lsof -nP -iTCP:5222 -sTCP:LISTEN` and `lsof -nP -iTCP:5269 -sTCP:LISTEN`

---

## Daily Run Workflow

For later runs (after first-time setup):

```bash
source .venv/bin/activate
docker start prosody
python main.py
```

To stop everything:

```bash
docker stop prosody
deactivate
```

---

## Simulated Time

The environment runs at **60x real time** (1 real second = 1 simulated minute).
A 2-minute real run covers approximately 2 simulated hours.

You can change this by editing `_time_speed` in `simulation/environment.py`.

---

*DCIT 403 Semester Project — Prometheus Methodology*
*Platform: Python 3.9+ | SPADE 3.3+ | XMPP server: local Prosody (Docker)*
