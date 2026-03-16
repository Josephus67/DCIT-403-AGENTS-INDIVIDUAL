"""
simulation/environment.py
─────────────────────────
Simulates the physical campus environment:
  - Room occupancy sensors
  - Device states (lights, AC, projector)
  - Room timetable / schedule
  - Actuator interface (accept device commands, return ACK/NACK)

The MonitorAgent reads from this module.
The DecisionAgent writes commands back to it.
In a real deployment this would be replaced by actual hardware APIs.
"""

import threading
import time
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


# ─────────────────────────────────────────────
# Room definitions
# ─────────────────────────────────────────────

ROOMS = ["LH-1", "LH-2", "LAB-A", "LAB-B", "OFFICE-1", "CORRIDOR-N"]

# Schedule: list of (weekday 0=Mon, start_hour, end_hour)
# Simplified to hour-level for simulation
SCHEDULE: Dict[str, list] = {
    "LH-1":       [(0, 9, 10), (0, 13, 15), (1, 8, 10), (2, 11, 13)],
    "LH-2":       [(0, 10, 12), (1, 14, 16), (3, 9, 11)],
    "LAB-A":      [(0, 8, 12), (2, 8, 12), (4, 8, 12)],
    "LAB-B":      [(1, 9, 13), (3, 13, 17)],
    "OFFICE-1":   [(0, 8, 17), (1, 8, 17), (2, 8, 17), (3, 8, 17), (4, 8, 17)],
    "CORRIDOR-N": [],  # Always monitored, never scheduled
}

# Device states per room: lights, AC, projector
DeviceState = Dict[str, str]  # e.g. {"lights": "on", "AC": "on", "projector": "off"}

# Simulated fault probability per command (5% chance of NACK)
FAULT_PROBABILITY = 0.05


class Environment:
    """
    Thread-safe simulated campus environment.
    Holds room states and processes device commands.
    """

    def __init__(self):
        self._lock = threading.Lock()

        # Initialise all rooms as unoccupied with all devices on
        # (simulates a building that was never properly shut down)
        self._room_states: Dict[str, Dict[str, Any]] = {
            room: {
                "occupied": False,
                "occupancy_count": 0,
                "devices": {
                    "lights": "on",
                    "AC": "on",
                    "projector": "on" if "LH" in room or "LAB" in room else "off",
                },
                "device_faults": set(),
            }
            for room in ROOMS
        }

        # Start background thread that evolves occupancy over simulated time
        self._sim_time = datetime.now().replace(hour=8, minute=0, second=0)
        self._running = True
        self._time_speed = 60  # 1 real second = 60 sim seconds (1 sim hour per minute)
        self._thread = threading.Thread(target=self._evolve, daemon=True)
        self._thread.start()

    # ── Public sensor API (read by MonitorAgent) ──────────────────────────

    def get_room_state(self, room_id: str) -> Optional[Dict[str, Any]]:
        """Return a snapshot of the room's current state."""
        with self._lock:
            state = self._room_states.get(room_id)
            if state is None:
                return None
            return {
                "room_id": room_id,
                "occupied": state["occupied"],
                "occupancy_count": state["occupancy_count"],
                "devices": dict(state["devices"]),
                "sim_time": self._sim_time.strftime("%A %H:%M"),
            }

    def get_all_room_states(self) -> Dict[str, Dict[str, Any]]:
        """Return snapshots for all rooms."""
        return {room: self.get_room_state(room) for room in ROOMS}

    def get_schedule_status(self, room_id: str) -> str:
        """
        Returns one of:
          'active'    — a session is running right now
          'upcoming'  — session starts within the next 10 sim-minutes
          'idle'      — no session scheduled soon
        """
        with self._lock:
            now = self._sim_time
            weekday = now.weekday()
            hour = now.hour
            minute = now.minute

        for (day, start, end) in SCHEDULE.get(room_id, []):
            if day != weekday:
                continue
            if start <= hour < end:
                return "active"
            # Upcoming: within next 10 sim-minutes (~10 real seconds at 60x speed)
            minutes_until = (start - hour) * 60 - minute
            if 0 < minutes_until <= 10:
                return "upcoming"
        return "idle"

    def is_outside_hours(self, room_id: str) -> bool:
        """True if the room is occupied but has no scheduled session."""
        status = self.get_schedule_status(room_id)
        state = self.get_room_state(room_id)
        return state["occupied"] and status == "idle"

    # ── Actuator API (written by DecisionAgent) ───────────────────────────

    def send_device_command(
        self, room_id: str, device: str, action: str
    ) -> Dict[str, Any]:
        """
        Attempt to set a device state.
        Returns {"ack": True} or {"ack": False, "reason": "..."}.
        Simulates a small fault probability.
        """
        if room_id not in self._room_states:
            return {"ack": False, "reason": f"Unknown room {room_id}"}

        if random.random() < FAULT_PROBABILITY:
            return {"ack": False, "reason": "Device unresponsive (simulated fault)"}

        with self._lock:
            self._room_states[room_id]["devices"][device] = action

        return {"ack": True}

    def get_sim_time(self) -> str:
        with self._lock:
            return self._sim_time.strftime("%A %H:%M")

    def stop(self):
        self._running = False

    # ── Internal simulation loop ──────────────────────────────────────────

    def _evolve(self):
        """
        Advances simulated time and randomly changes occupancy
        to create realistic scenarios for the agents to respond to.
        """
        while self._running:
            time.sleep(1)  # 1 real second
            with self._lock:
                self._sim_time += timedelta(seconds=self._time_speed)
                self._update_occupancy()

    def _update_occupancy(self):
        """Adjust room occupancy based on schedule and some randomness."""
        now = self._sim_time
        weekday = now.weekday()
        hour = now.hour

        for room in ROOMS:
            scheduled = any(
                day == weekday and start <= hour < end
                for (day, start, end) in SCHEDULE.get(room, [])
            )

            # Outside normal hours (before 7am or after 10pm) — mostly empty
            if hour < 7 or hour >= 22:
                # 3% chance of anomalous occupancy (simulates Scenario 2)
                occupied = random.random() < 0.03
            elif scheduled:
                # During scheduled session: 85% chance occupied
                occupied = random.random() < 0.85
            else:
                # Unscheduled hours: 10% chance someone lingering
                occupied = random.random() < 0.10

            count = random.randint(5, 40) if occupied else 0
            self._room_states[room]["occupied"] = occupied
            self._room_states[room]["occupancy_count"] = count
