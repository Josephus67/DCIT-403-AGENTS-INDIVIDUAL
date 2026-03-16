"""
utils/logger.py
───────────────
Structured event logger for the AlertAgent.
Writes log entries to both stdout and a local log file (energy_monitor.log).
"""

import json
import logging
import os
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "energy_monitor.log")

# Configure file + console logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
    ],
)

_logger = logging.getLogger("EnergyMonitor")


def log_event(event_type: str, room_id: str, detail: str, priority: str = "LOW"):
    entry = {
        "event": event_type,
        "room": room_id,
        "detail": detail,
        "priority": priority,
        "time": datetime.now().isoformat(),
    }
    prefix = {
        "LOW":    "📋",
        "MEDIUM": "⚠️ ",
        "HIGH":   "🚨",
    }.get(priority, "ℹ️ ")
    _logger.info(f"{prefix}  [{event_type}] {room_id}: {detail}")
    return entry


def log_fault(room_id: str, device: str, detail: str):
    _logger.warning(f"🔧  [FAULT] {room_id}/{device}: {detail}")


def log_notification(target: str, message: str):
    _logger.info(f"📣  [NOTIFY → {target}]: {message}")
