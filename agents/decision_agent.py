"""
agents/decision_agent.py
─────────────────────────
DecisionAgent
=============
Prometheus role: Reason about the environment state and act.

Behaviours
──────────
  ReceiveStateBehaviour     — listens for ROOM_STATE_UPDATE messages,
                              evaluates each room against goals,
                              triggers device commands and alert requests.

  PeakHourBehaviour         — periodic check; activates/deactivates
                              load-shedding plan (Plan P4).

Plans implemented
─────────────────
  P1 — Unoccupied room with devices on → switch off / reduce devices
  P2 — Room becomes occupied → restore full power
  P3 — Retry on device command NACK (up to 1 retry, then MAINTENANCE alert)
  P4 — Peak-hour load shedding (12:00–14:00 weekdays)

Goals handled: G1.2, G1.3, G2.2, G3.1
Percepts used: P8 (ACK), P9 (ROOM_STATE_UPDATE), P12 (peak hour timer)
Actions performed: A3–A9, A13, A14

XMPP JID:  cem_decision@jabber.ccc.de
"""

import asyncio
import json
from datetime import datetime

import spade
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
from spade.message import Message
from spade.template import Template

from simulation.environment import Environment
from utils.messages import (
    make_alert_request,
    parse_body,
    ONTOLOGY_ENERGY,
    LANG_JSON,
    INFORM,
    REQUEST,
    MSG_ROOM_STATE,
    ALERT_LOG,
    ALERT_SECURITY,
    ALERT_MAINTENANCE,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    PRIORITY_HIGH,
)

# Peak hour window (simulated hour integers)
PEAK_START = 12
PEAK_END   = 14

# Device command retry timeout (real seconds)
RETRY_TIMEOUT = 10

# Minimum occupancy to apply load shedding to a room
PEAK_SHEDDING_THRESHOLD = 5


class DecisionAgent(Agent):
    """
    Core reasoning agent.
    Receives room state reports, applies goal-driven plans,
    issues device commands, and delegates alerts.
    """

    def __init__(self, jid: str, password: str, environment: Environment,
                 alert_jid: str, **kwargs):
        super().__init__(jid, password, **kwargs)

        self.environment = environment
        self.alert_jid = alert_jid

        # Belief: retry counters per (room, device)
        self.pending_retries: dict = {}

        # Belief: whether peak-hour plan is currently active
        self.peak_active: bool = False

    async def setup(self):
        print(f"[DecisionAgent] Online as {self.jid}")

        # Template: accept INFORM messages with our ontology
        template = Template()
        template.set_metadata("ontology", ONTOLOGY_ENERGY)
        template.set_metadata("performative", INFORM)

        self.add_behaviour(self.ReceiveStateBehaviour(), template)
        self.add_behaviour(self.PeakHourBehaviour(period=10))  # check every 10s real

    # ── Helper: send an alert request to AlertAgent ───────────────────────

    async def _send_alert(self, sender_behaviour, alert_type: str, priority: str,
                          room_id: str, detail: str):
        body = make_alert_request(alert_type, priority, room_id, detail)
        msg  = Message(to=self.alert_jid)
        msg.set_metadata("ontology", ONTOLOGY_ENERGY)
        msg.set_metadata("language", LANG_JSON)
        msg.set_metadata("performative", REQUEST)
        msg.body = body
        await sender_behaviour.send(msg)

    # ── Helper: issue a device command with retry logic (Plan P3) ─────────

    async def _command_device(self, sender_behaviour, room_id: str, device: str, action: str):
        """
        Issue a device command to the environment.
        Retries once on NACK. Sends MAINTENANCE alert on second failure.
        Implements Plans P1/P2/P3.
        """
        result = self.environment.send_device_command(room_id, device, action)

        if result["ack"]:
            print(f"[DecisionAgent]   ✓ {room_id}/{device} → {action}")
            # A7: Log the successful action
            await self._send_alert(
                sender_behaviour,
                ALERT_LOG, PRIORITY_LOW, room_id,
                f"Device command executed: {device} → {action}"
            )
        else:
            key = (room_id, device)
            retries = self.pending_retries.get(key, 0)

            if retries < 1:
                # Plan P3 step 2: retry once
                self.pending_retries[key] = retries + 1
                print(f"[DecisionAgent]   ↻ NACK for {room_id}/{device}, retrying...")
                await asyncio.sleep(5)
                retry_result = self.environment.send_device_command(room_id, device, action)

                if retry_result["ack"]:
                    print(f"[DecisionAgent]   ✓ {room_id}/{device} → {action} (retry OK)")
                    self.pending_retries.pop(key, None)
                    await self._send_alert(
                        sender_behaviour,
                        ALERT_LOG, PRIORITY_LOW, room_id,
                        f"Device command succeeded on retry: {device} → {action}"
                    )
                else:
                    # Plan P3 step 3: escalate to MAINTENANCE
                    self.pending_retries[key] = 2
                    print(f"[DecisionAgent]   ✗ {room_id}/{device} — sending MAINTENANCE alert")
                    await self._send_alert(
                        sender_behaviour,
                        ALERT_MAINTENANCE, PRIORITY_HIGH, room_id,
                        f"Device unresponsive after retry: {device}. Manual check required."
                    )
            else:
                print(f"[DecisionAgent]   ✗ {room_id}/{device} — already faulted, skipping")

    # ── Behaviour 1: Receive and evaluate room state ───────────────────────

    class ReceiveStateBehaviour(CyclicBehaviour):
        """
        Listens for ROOM_STATE_UPDATE messages from MonitorAgent.
        Applies Plans P1 and P2 based on occupancy and schedule status.
        """

        async def run(self):
            msg = await self.receive(timeout=30)
            if msg is None:
                return

            data = parse_body(msg.body)
            if data.get("type") != MSG_ROOM_STATE:
                return

            agent: DecisionAgent = self.agent
            room_id        = data["room_id"]
            occupied       = data["occupied"]
            occupancy_count = data.get("occupancy_count", 0)
            devices        = data["devices"]
            schedule_status = data["schedule_status"]
            sim_time       = data.get("sim_time", "?")

            print(f"\n[DecisionAgent] Evaluating {room_id} | "
                  f"Occupied: {occupied} ({occupancy_count}) | "
                  f"Schedule: {schedule_status} | Time: {sim_time}")

            # ── Plan P1: Unoccupied room with devices on ───────────────
            if not occupied and schedule_status == "idle":
                actions_needed = {}

                if devices.get("lights") == "on":
                    actions_needed["lights"] = "dim"
                if devices.get("AC") in ("on",):
                    actions_needed["AC"] = "eco"
                if devices.get("projector") == "on":
                    actions_needed["projector"] = "off"

                if actions_needed:
                    print(f"[DecisionAgent]  → Plan P1: Reducing devices in {room_id}")
                    for device, action in actions_needed.items():
                        await agent._command_device(self, room_id, device, action)

            # ── Plan P2: Room becomes occupied ────────────────────────
            elif occupied:
                actions_needed = {}

                if devices.get("lights") in ("off", "dim"):
                    actions_needed["lights"] = "on"
                if devices.get("AC") in ("off", "eco"):
                    actions_needed["AC"] = "on"
                if (devices.get("projector") == "off"
                        and ("LH" in room_id or "LAB" in room_id)):
                    actions_needed["projector"] = "on"

                if actions_needed:
                    print(f"[DecisionAgent]  → Plan P2: Restoring devices in {room_id}")
                    for device, action in actions_needed.items():
                        await agent._command_device(self, room_id, device, action)

            # ── Upcoming session: do nothing (room will be needed soon) ─
            elif not occupied and schedule_status == "upcoming":
                print(f"[DecisionAgent]  → Session upcoming in {room_id}, holding current state")

    # ── Behaviour 2: Peak-hour load shedding (Plan P4) ───────────────────

    class PeakHourBehaviour(PeriodicBehaviour):
        """
        Checks every 10 real seconds whether simulated time is in
        the peak-hour window. Activates or deactivates load shedding.
        """

        async def run(self):
            agent: DecisionAgent = self.agent
            sim_time_str = agent.environment.get_sim_time()

            # Parse simulated hour from "Weekday HH:MM"
            try:
                parts = sim_time_str.split(" ")
                hour = int(parts[-1].split(":")[0])
                weekday = parts[0]
                is_weekday = weekday not in ("Saturday", "Sunday")
            except (IndexError, ValueError):
                return

            in_peak = is_weekday and PEAK_START <= hour < PEAK_END

            # Activate load shedding
            if in_peak and not agent.peak_active:
                agent.peak_active = True
                print(f"\n[DecisionAgent] 🔋 PEAK HOUR — activating load shedding ({sim_time_str})")
                all_states = agent.environment.get_all_room_states()

                for room_id, state in all_states.items():
                    if state["occupied"] and state["occupancy_count"] < PEAK_SHEDDING_THRESHOLD:
                        print(f"[DecisionAgent]  → Shedding load in {room_id} "
                              f"(occupancy: {state['occupancy_count']})")
                        await agent._command_device(self, room_id, "AC", "eco")
                        await agent._send_alert(
                            self,
                            ALERT_LOG, PRIORITY_MEDIUM, room_id,
                            f"Peak-hour load shedding: AC reduced to eco mode "
                            f"(occupancy={state['occupancy_count']})"
                        )

            # Deactivate load shedding
            elif not in_peak and agent.peak_active:
                agent.peak_active = False
                print(f"\n[DecisionAgent] ✅ Peak hour ended — restoring normal settings ({sim_time_str})")
                all_states = agent.environment.get_all_room_states()

                for room_id, state in all_states.items():
                    if state["occupied"] and state["devices"].get("AC") == "eco":
                        await agent._command_device(self, room_id, "AC", "on")
                        await agent._send_alert(
                            self,
                            ALERT_LOG, PRIORITY_LOW, room_id,
                            "Post-peak: AC restored to full cooling"
                        )
