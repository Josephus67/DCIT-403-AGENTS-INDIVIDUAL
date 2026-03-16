"""
agents/alert_agent.py
──────────────────────
AlertAgent
==========
Prometheus role: Handle all outbound notifications and structured logging.

Behaviours
──────────
  ReceiveAlertBehaviour   — listens for ALERT_REQUEST (from DecisionAgent)
                            and ANOMALY_FLAG (from MonitorAgent).
                            Routes to appropriate handler based on alert type.

Goals handled: G3.2, G3.3
Percepts used: P10 (ALERT_REQUEST), P11 (ANOMALY_FLAG)
Actions performed: A10 (write log), A11 (notify staff), A12 (fault registry)

XMPP JID:  cem_alert@jabber.ccc.de
"""

import json
from datetime import datetime

import spade
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template

from utils.messages import (
    parse_body,
    ONTOLOGY_ENERGY,
    LANG_JSON,
    REQUEST,
    ALERT,
    MSG_ALERT_REQUEST,
    MSG_ANOMALY,
    ALERT_LOG,
    ALERT_SECURITY,
    ALERT_MAINTENANCE,
    PRIORITY_HIGH,
    PRIORITY_MEDIUM,
    PRIORITY_LOW,
)
from utils.logger import log_event, log_fault, log_notification


class AlertAgent(Agent):
    """
    Receives ALERT_REQUEST and ANOMALY_FLAG messages.
    Logs all events, notifies facilities/security staff for HIGH priority,
    and maintains a fault registry for unresponsive devices.
    """

    def __init__(self, jid: str, password: str, **kwargs):
        super().__init__(jid, password, **kwargs)

        # Belief: fault registry {device_key: {room_id, time, count}}
        self.fault_registry: dict = {}

        # Belief: full structured log
        self.event_log: list = []

    async def setup(self):
        print(f"[AlertAgent] Online as {self.jid}")

        # Accept both REQUEST (ALERT_REQUEST) and ALERT (ANOMALY_FLAG)
        template_request = Template()
        template_request.set_metadata("ontology", ONTOLOGY_ENERGY)
        template_request.set_metadata("performative", REQUEST)

        template_alert = Template()
        template_alert.set_metadata("ontology", ONTOLOGY_ENERGY)
        template_alert.set_metadata("performative", ALERT)

        # Combine templates with OR
        combined = template_request | template_alert
        self.add_behaviour(self.ReceiveAlertBehaviour(), combined)

    # ── Behaviour ────────────────────────────────────────────────────────

    class ReceiveAlertBehaviour(CyclicBehaviour):
        """
        Listens for both ALERT_REQUEST and ANOMALY_FLAG messages.
        Routes each to the correct handler.
        """

        async def run(self):
            msg = await self.receive(timeout=30)
            if msg is None:
                return

            agent: AlertAgent = self.agent
            data = parse_body(msg.body)
            msg_type = data.get("type")

            if msg_type == MSG_ALERT_REQUEST:
                await agent._handle_alert_request(data)
            elif msg_type == MSG_ANOMALY:
                await agent._handle_anomaly_flag(data)
            else:
                print(f"[AlertAgent] Unknown message type: {msg_type}")

    # ── Handlers ─────────────────────────────────────────────────────────

    async def _handle_alert_request(self, data: dict):
        """
        Handle ALERT_REQUEST from DecisionAgent.
        Routes to log, maintenance, or security handler.
        """
        alert_type = data.get("alert_type", ALERT_LOG)
        priority   = data.get("priority", PRIORITY_LOW)
        room_id    = data.get("room_id", "UNKNOWN")
        detail     = data.get("detail", "")

        # A10: Log the event
        entry = log_event(alert_type, room_id, detail, priority)
        self.event_log.append(entry)

        # A11: Notify staff for MAINTENANCE or SECURITY
        if alert_type == ALERT_MAINTENANCE:
            self._notify_staff(
                target="Facilities Management",
                message=f"[MAINTENANCE REQUIRED] {room_id}: {detail}",
                priority=priority,
            )
            # A12: Register in fault registry
            self._register_fault(room_id, detail)

        elif alert_type == ALERT_SECURITY:
            self._notify_staff(
                target="Security Desk",
                message=f"[SECURITY ALERT] {room_id}: Unauthorised occupancy detected. {detail}",
                priority=priority,
            )

    async def _handle_anomaly_flag(self, data: dict):
        """
        Handle ANOMALY_FLAG from MonitorAgent.
        Always treated as a high-priority security event.
        """
        room_id    = data.get("room_id", "UNKNOWN")
        sim_time   = data.get("sim_time", "?")
        count      = data.get("occupancy_count", 0)

        detail = (
            f"Occupancy detected outside scheduled hours at {sim_time}. "
            f"Approx {count} person(s) present. No booking found."
        )

        # A10: Log
        entry = log_event(ALERT_SECURITY, room_id, detail, PRIORITY_HIGH)
        self.event_log.append(entry)

        # A11: Notify security
        self._notify_staff(
            target="Security Desk",
            message=f"[ANOMALY] {room_id} at {sim_time}: {detail}",
            priority=PRIORITY_HIGH,
        )

    # ── Internal helpers ──────────────────────────────────────────────────

    def _notify_staff(self, target: str, message: str, priority: str):
        """
        Simulates sending a notification to staff.
        In production: replace with email/SMS/Slack API call.
        """
        log_notification(target, message)
        # Notification record stored in log for audit
        self.event_log.append({
            "event": "NOTIFICATION_SENT",
            "target": target,
            "message": message,
            "priority": priority,
            "time": datetime.now().isoformat(),
        })

    def _register_fault(self, room_id: str, detail: str):
        """
        A12: Add or update a device fault entry in the fault registry.
        Extracts device name from the detail string if possible.
        """
        device = "unknown"
        for d in ("lights", "AC", "projector"):
            if d in detail.lower():
                device = d
                break

        key = f"{room_id}::{device}"
        if key not in self.fault_registry:
            self.fault_registry[key] = {
                "room_id": room_id,
                "device": device,
                "first_reported": datetime.now().isoformat(),
                "count": 1,
                "unresolved": True,
                "detail": detail,
            }
        else:
            self.fault_registry[key]["count"] += 1
            self.fault_registry[key]["detail"] = detail

        log_fault(room_id, device, detail)
        print(f"[AlertAgent] 🗂️  Fault registry updated: {key} "
              f"(total reports: {self.fault_registry[key]['count']})")

    def get_fault_summary(self) -> str:
        """Return a human-readable fault registry summary."""
        if not self.fault_registry:
            return "No faults registered."
        lines = ["\n=== Fault Registry ==="]
        for key, rec in self.fault_registry.items():
            lines.append(
                f"  {key}  | reports: {rec['count']} | "
                f"unresolved: {rec['unresolved']} | {rec['detail'][:60]}"
            )
        return "\n".join(lines)

    def get_log_summary(self, last_n: int = 10) -> str:
        """Return the last N log entries as a formatted string."""
        entries = self.event_log[-last_n:]
        if not entries:
            return "No log entries yet."
        lines = [f"\n=== Last {len(entries)} Log Entries ==="]
        for e in entries:
            lines.append(
                f"  [{e.get('time','?')[:19]}] "
                f"{e.get('event','?'):15s} | "
                f"{e.get('room', e.get('target','?')):12s} | "
                f"{str(e.get('detail', e.get('message','')))[:60]}"
            )
        return "\n".join(lines)
