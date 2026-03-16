"""
utils/messages.py
─────────────────
Defines all message types and helper constructors used across agents.
Maps directly to the message structure defined in Phase 3.

Message types
─────────────
  ROOM_STATE_UPDATE   MonitorAgent  → DecisionAgent
  ANOMALY_FLAG        MonitorAgent  → AlertAgent
  ALERT_REQUEST       DecisionAgent → AlertAgent

All messages are serialised as JSON strings in the SPADE message body.
"""

import json
from datetime import datetime


# ── Ontology / performative constants ────────────────────────────────────

ONTOLOGY_ENERGY   = "campus-energy-monitor"
LANG_JSON         = "json"

# Performatives (re-use FIPA standard names)
INFORM   = "inform"
REQUEST  = "request"
ALERT    = "alert"

# Message type tags (stored inside the body JSON)
MSG_ROOM_STATE    = "ROOM_STATE_UPDATE"
MSG_ANOMALY       = "ANOMALY_FLAG"
MSG_ALERT_REQUEST = "ALERT_REQUEST"

# Alert types (used in ALERT_REQUEST)
ALERT_LOG         = "LOG"
ALERT_SECURITY    = "SECURITY"
ALERT_MAINTENANCE = "MAINTENANCE"

# Priority levels
PRIORITY_LOW    = "LOW"
PRIORITY_MEDIUM = "MEDIUM"
PRIORITY_HIGH   = "HIGH"


# ── Message body constructors ─────────────────────────────────────────────

def make_room_state_update(
    room_id: str,
    occupied: bool,
    occupancy_count: int,
    devices: dict,
    schedule_status: str,
    sim_time: str,
) -> str:
    """Serialise a ROOM_STATE_UPDATE message body."""
    return json.dumps({
        "type": MSG_ROOM_STATE,
        "room_id": room_id,
        "occupied": occupied,
        "occupancy_count": occupancy_count,
        "devices": devices,
        "schedule_status": schedule_status,
        "sim_time": sim_time,
        "timestamp": datetime.now().isoformat(),
    })


def make_anomaly_flag(
    room_id: str,
    sim_time: str,
    occupancy_count: int,
) -> str:
    """Serialise an ANOMALY_FLAG message body."""
    return json.dumps({
        "type": MSG_ANOMALY,
        "room_id": room_id,
        "sim_time": sim_time,
        "occupied": True,
        "scheduled": False,
        "occupancy_count": occupancy_count,
        "timestamp": datetime.now().isoformat(),
    })


def make_alert_request(
    alert_type: str,
    priority: str,
    room_id: str,
    detail: str,
) -> str:
    """Serialise an ALERT_REQUEST message body."""
    return json.dumps({
        "type": MSG_ALERT_REQUEST,
        "alert_type": alert_type,
        "priority": priority,
        "room_id": room_id,
        "detail": detail,
        "timestamp": datetime.now().isoformat(),
    })


def parse_body(body: str) -> dict:
    """Parse a JSON message body. Returns empty dict on failure."""
    try:
        return json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return {}
