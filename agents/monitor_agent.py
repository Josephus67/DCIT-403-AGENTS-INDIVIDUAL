"""
agents/monitor_agent.py
────────────────────────
MonitorAgent
============
Prometheus role: Perceive the environment.

Behaviours
──────────
  PeriodicSensorBehaviour   — polls all room states every POLL_INTERVAL seconds,
                              sends ROOM_STATE_UPDATE to DecisionAgent for each room,
                              sends ANOMALY_FLAG to AlertAgent when outside-hours
                              occupancy is detected.

Goals handled: G1.1, G2.1
Percepts used: P1–P7 (occupancy, device states, time, schedule)
Actions performed: A1 (ROOM_STATE_UPDATE), A2 (ANOMALY_FLAG)

XMPP JID:  cem_monitor@jabber.ccc.de
"""

import asyncio
import spade
from spade.agent import Agent
from spade.behaviour import PeriodicBehaviour
from spade.message import Message

from simulation.environment import Environment, ROOMS
from utils.messages import (
    make_room_state_update,
    make_anomaly_flag,
    ONTOLOGY_ENERGY,
    LANG_JSON,
    INFORM,
    ALERT,
)

# How often to poll (real seconds). At 60x sim speed, 5s real ≈ 5 sim minutes.
POLL_INTERVAL = 5


class MonitorAgent(Agent):
    """
    Perceives room occupancy, device states, and schedules.
    Forwards consolidated state to DecisionAgent every POLL_INTERVAL seconds.
    Independently flags anomalies directly to AlertAgent.
    """

    def __init__(self, jid: str, password: str, environment: Environment,
                 decision_jid: str, alert_jid: str, **kwargs):
        super().__init__(jid, password, **kwargs)

        self.environment = environment
        self.decision_jid = decision_jid
        self.alert_jid = alert_jid

    async def setup(self):
        print(f"[MonitorAgent] Online as {self.jid}")
        poll = self.PeriodicSensorBehaviour(period=POLL_INTERVAL)
        self.add_behaviour(poll)

    # ── Behaviour ────────────────────────────────────────────────────────

    class PeriodicSensorBehaviour(PeriodicBehaviour):
        """
        Runs every POLL_INTERVAL seconds.
        For each room:
          1. Read current state from the environment
          2. Determine schedule status
          3. If anomaly detected → send ANOMALY_FLAG to AlertAgent
          4. Send ROOM_STATE_UPDATE to DecisionAgent
        """

        async def run(self):
            agent: MonitorAgent = self.agent

            for room_id in ROOMS:
                state = agent.environment.get_room_state(room_id)
                if state is None:
                    continue

                schedule_status = agent.environment.get_schedule_status(room_id)
                outside_hours  = agent.environment.is_outside_hours(room_id)

                # ── A2: Send ANOMALY_FLAG if occupied outside schedule ──
                if outside_hours:
                    flag_body = make_anomaly_flag(
                        room_id=room_id,
                        sim_time=state["sim_time"],
                        occupancy_count=state["occupancy_count"],
                    )
                    flag_msg = Message(to=agent.alert_jid)
                    flag_msg.set_metadata("ontology", ONTOLOGY_ENERGY)
                    flag_msg.set_metadata("language", LANG_JSON)
                    flag_msg.set_metadata("performative", ALERT)
                    flag_msg.body = flag_body
                    await self.send(flag_msg)

                # ── A1: Send ROOM_STATE_UPDATE to DecisionAgent ──
                update_body = make_room_state_update(
                    room_id=room_id,
                    occupied=state["occupied"],
                    occupancy_count=state["occupancy_count"],
                    devices=state["devices"],
                    schedule_status=schedule_status,
                    sim_time=state["sim_time"],
                )
                update_msg = Message(to=agent.decision_jid)
                update_msg.set_metadata("ontology", ONTOLOGY_ENERGY)
                update_msg.set_metadata("language", LANG_JSON)
                update_msg.set_metadata("performative", INFORM)
                update_msg.body = update_body
                await self.send(update_msg)

            sim_time = agent.environment.get_sim_time()
            print(f"[MonitorAgent] Polled {len(ROOMS)} rooms | Sim time: {sim_time}")
