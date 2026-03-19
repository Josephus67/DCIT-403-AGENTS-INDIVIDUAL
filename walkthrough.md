# Smart Campus Energy Monitor
### DCIT 403 — Intelligent Agent Project (Prometheus Methodology)

A **multi-agent system** that simulates a campus energy management platform. The goal is to:

- Monitor room occupancy and device usage (lights, AC, projectors)
- Automatically reduce energy waste in unoccupied rooms
- Detect anomalous (outside-schedule) occupancy and alert security
- Track device faults across the system

This project runs locally using **SPADE agents** and a **local Prosody XMPP server** (in Docker) to simulate agent communication.

---

## 🧠 System Architecture (From Beginning to End)

This system is built around three cooperative agents communicating over XMPP using **FIPA-style messages**. At a high level:

1. **Environment (simulation)** produces a continuous stream of room data (occupancy, devices, schedule)
2. **MonitorAgent** reads the environment periodically and reports room states
3. **DecisionAgent** receives room state updates, reasons over goals/plans, and issues device commands or alerts
4. **AlertAgent** logs events, notifies staff, and maintains a fault registry

### Core concepts

- **Percepts**: sensor readings (occupancy, device state, schedule, time)
- **Plans**: goal-driven behaviors for reducing waste, responding to occupancy, and handling faults
- **Actions**: sending messages, changing device states in simulation, and notifying staff

---

## 📦 Project Modules (What does each part do?)

### `main.py` — Orchestrator

- Initializes the **simulated environment** (`simulation/environment.py`)
- Instantiates the three agents and connects them to the local XMPP server
- Runs the simulation for a configured amount of real time
- Prints summaries and a final report (log + fault registry)

### `simulation/environment.py` — Simulated campus

This module simulates:

- **Rooms** (lecture halls, labs, office, corridor)
- **Schedule** (weekday sessions in rooms)
- **Occupancy** (randomized based on schedule)
- **Devices** (lights, AC, projector) with simulated faults

Key behaviors:

- Time advances ~60× faster than real time (1 real second = 1 simulated minute)
- Rooms transition between occupied/unoccupied according to schedule + randomness
- Device commands from `DecisionAgent` are applied with a small chance of failure (NACK)

***Why?***
This lets agents make decisions in a “real-time” loop without waiting hours.

### `agents/monitor_agent.py` — Perception

**MonitorAgent** polls the environment every 5 real seconds (≈5 simulated minutes):

1. Reads each room’s state (occupancy, devices, simulated time)
2. Computes schedule status (`active`, `upcoming`, `idle`)
3. Sends **ROOM_STATE_UPDATE** messages to `DecisionAgent`
4. Sends **ANOMALY_FLAG** messages to `AlertAgent` when occupancy occurs outside scheduled hours

This is the “sensor” in the system.

### `agents/decision_agent.py` — Reasoning & action

**DecisionAgent** receives room state updates and applies a set of plans:

- **P1: Unoccupied room → energy reduction**
  - If room is idle and empty, switch lights to `dim`, AC to `eco`, projector off.

- **P2: Occupied room → restore full power**
  - When occupancy appears, restore lights/AC/projector (for labs and lecture halls).

- **P3: Command retry logic (fault handling)**
  - If a device command fails (NACK), retry once.
  - If it still fails, raise a **MAINTENANCE** alert.

- **P4: Peak-hour load shedding**
  - During simulated peak hours (12:00–14:00 weekdays), reduce AC to `eco` in lightly occupied rooms.

When actions occur, DecisionAgent sends **ALERT_REQUEST** messages to `AlertAgent`.

### `agents/alert_agent.py` — Logging & alerts

**AlertAgent** receives both:

- **ANOMALY_FLAG** messages (MonitorAgent)
- **ALERT_REQUEST** messages (DecisionAgent)

It performs three jobs:

1. **Logs events** (via `utils/logger.py`) into a structured log and a file `energy_monitor.log`
2. **Sends “notifications”** to simulated staff (console output)
3. **Tracks faults** in a fault registry (unresponsive devices)

---

## 🗂️ Message Protocol (How agents talk)

All inter-agent communication is encoded as JSON in the SPADE message body.

### Message types

| Message | Sender | Receiver | Purpose |
|---------|--------|----------|---------|
| `ROOM_STATE_UPDATE` | MonitorAgent → DecisionAgent | Send current room state
| `ANOMALY_FLAG` | MonitorAgent → AlertAgent | Flag occupancy outside schedule
| `ALERT_REQUEST` | DecisionAgent → AlertAgent | Log events / request notification / register fault

### Message structure

Each message includes:
- `type` (one of the message tags)
- `room_id` and timestamp
- `occupancy_count`, `devices`, `schedule_status` (for ROOM_STATE_UPDATE)
- `alert_type`, `priority`, `detail` (for ALERT_REQUEST)

This protocol is defined in `utils/messages.py`.

---

## ✅ Running the system (Full walkthrough)

### 1) Prepare the environment

**Requirements:**
- Python 3.9+
- `pip`
- Docker

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Start local XMPP server (Prosody)

```bash
docker rm -f prosody 2>/dev/null || true
docker run -d --name prosody -p 5222:5222 -p 5269:5269 prosody/prosody:latest
sleep 2
docker exec prosody prosodyctl register cem_monitor localhost 123
docker exec prosody prosodyctl register cem_decision localhost 123
docker exec prosody prosodyctl register cem_alert localhost 123
```

### 3) Start the simulation

```bash
python main.py
```

### Optional run flags

- `--duration <seconds>` — how long to run (0 for forever)
- `--monitor-jid`, `--monitor-pwd`, `--decision-jid`, `--decision-pwd`, `--alert-jid`, `--alert-pwd` — override credentials

Example:

```bash
python main.py --duration 300
```

### Expected output

You should see logs like:

- `Agent cem_alert@localhost connected and authenticated.`
- `Agent cem_decision@localhost connected and authenticated.`
- `Agent cem_monitor@localhost connected and authenticated.`

And periodic summaries of activity and any faults.

---

## 🔍 How to Extend / Customize

### Add a new room

1. Add its name to `simulation/environment.py`’s `ROOMS` list.
2. Update its schedule in `SCHEDULE`.
3. Optionally tune its default device states.

### Add a new device type (e.g., blinds)

1. Add the device state to the room initialization in `Environment.__init__`.
2. Update `MonitorAgent` to include it in the reported state.
3. Update `DecisionAgent` to decide actions for it.

### Replace the Simulated Environment with real hardware

- Implement the same public interface as `Environment`:
  - `get_room_state(room_id)`
  - `get_schedule_status(room_id)`
  - `send_device_command(room_id, device, action)`
  - `get_sim_time()`

Then inject that implementation in `main.py` when constructing `MonitorAgent` and `DecisionAgent`.

---

## 🧪 Troubleshooting

- **Agents fail to authenticate**: Ensure Prosody is running and the user accounts exist.
- **Port conflicts on 5222/5269**: Stop other XMPP servers or change Docker port mappings.
- **`spade` import fails**: Ensure you installed dependencies in the active virtual environment.
- **Noise in logs**: The simulation is intentionally noisy to demonstrate state changes; most noise is normal.

---

## 🧩 Where to look for behavior mapping (Goals & Plans)

This project follows a “Prometheus”-style specification with explicit goals and plans. You can find the mapping in the source comments of each agent:

- `agents/monitor_agent.py` — perception goals
- `agents/decision_agent.py` — planning and acting goals
- `agents/alert_agent.py` — alerting and logging goals

---

## 🧾 Output & Logs

- **Console output** shows agent connection status, decisions, and alert notifications.
- **`energy_monitor.log`** (created in the repo root) contains structured log entries written by `utils/logger.py`.

---

## ✅ Summary (From start to finish)

1. Start Prosody (XMPP server) in Docker
2. Register the 3 agent accounts
3. Run `main.py` → this starts the simulation and agents
4. `MonitorAgent` reads the simulated campus, reports state + anomalies
5. `DecisionAgent` decides whether to save energy, restore power, or send alerts
6. `AlertAgent` logs events, notifies staff, and tracks faults
7. The system runs for the requested duration, then stops and prints a report

Enjoy experimenting with the simulation and extending the agent logic!

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
