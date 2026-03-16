"""
main.py
───────
Entry point for the Smart Campus Energy Monitor agent system.

Starts three SPADE agents against the jabber.ccc.de server:
  - MonitorAgent   (cem_monitor@jabber.ccc.de)
  - DecisionAgent  (cem_decision@jabber.ccc.de)
  - AlertAgent     (cem_alert@jabber.ccc.de)

A shared simulated Environment object is passed to MonitorAgent and
DecisionAgent so they can read sensors and issue commands respectively.

Usage
─────
  python main.py

  Or with custom credentials:
  python main.py --monitor-jid cem_monitor@jabber.ccc.de --monitor-pwd yourpassword ...

See README.md for full setup instructions.
"""

import asyncio
import argparse
import signal
import sys
import time

import spade

from simulation.environment import Environment
from agents.monitor_agent   import MonitorAgent
from agents.decision_agent  import DecisionAgent
from agents.alert_agent     import AlertAgent

# ── Default XMPP credentials ─────────────────────────────────────────────
# Change these to your registered jabber.ccc.de accounts before running.
DEFAULT_CREDS = {
    "monitor":  {"jid": "cem_monitor@localhost",  "pwd": "123"},
    "decision": {"jid": "cem_decision@localhost", "pwd": "123"},
    "alert":    {"jid": "cem_alert@localhost",    "pwd": "123"},
}

# How long to run the simulation (seconds). Set to 0 for indefinite.
SIM_DURATION = 120  # 2 real minutes ≈ 2 simulated hours at 60x speed


async def main(creds: dict):
    print("=" * 60)
    print("  Smart Campus Energy Monitor")
    print("  DCIT 403 — Intelligent Agent System (Prometheus)")
    print("=" * 60)
    print()

    # ── 1. Initialise simulated environment ──────────────────────────────
    print("[System] Initialising simulated environment...")
    env = Environment()
    await asyncio.sleep(1)  # allow environment thread to start

    # ── 2. Instantiate agents ─────────────────────────────────────────────
    alert_agent = AlertAgent(
        jid=creds["alert"]["jid"],
        password=creds["alert"]["pwd"],
    )

    decision_agent = DecisionAgent(
        jid=creds["decision"]["jid"],
        password=creds["decision"]["pwd"],
        environment=env,
        alert_jid=creds["alert"]["jid"],
    )

    monitor_agent = MonitorAgent(
        jid=creds["monitor"]["jid"],
        password=creds["monitor"]["pwd"],
        environment=env,
        decision_jid=creds["decision"]["jid"],
        alert_jid=creds["alert"]["jid"],
    )

    # ── 3. Start agents (AlertAgent first so it's ready to receive) ───────
    print("[System] Starting AlertAgent...")
    await alert_agent.start(auto_register=True)
    await asyncio.sleep(1)

    print("[System] Starting DecisionAgent...")
    await decision_agent.start(auto_register=True)
    await asyncio.sleep(1)

    print("[System] Starting MonitorAgent...")
    await monitor_agent.start(auto_register=True)

    print("\n[System] All agents running. Simulation in progress...")
    print(f"[System] Run duration: {SIM_DURATION}s real time "
          f"(≈ {SIM_DURATION * 60 // 3600:.0f}h {(SIM_DURATION * 60 % 3600) // 60:.0f}m simulated)")
    print("-" * 60)

    # ── 4. Run simulation ─────────────────────────────────────────────────
    try:
        if SIM_DURATION > 0:
            for elapsed in range(SIM_DURATION):
                await asyncio.sleep(1)
                # Print a summary every 30 seconds
                if (elapsed + 1) % 30 == 0:
                    _print_summary(alert_agent, env, elapsed + 1)
        else:
            # Run indefinitely
            while True:
                await asyncio.sleep(30)
                _print_summary(alert_agent, env, -1)

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n[System] Interrupted by user.")

    # ── 5. Shutdown ───────────────────────────────────────────────────────
    print("\n[System] Shutting down agents...")
    env.stop()
    await monitor_agent.stop()
    await decision_agent.stop()
    await alert_agent.stop()

    # Final summary
    print("\n" + "=" * 60)
    print("  SIMULATION COMPLETE — Final Report")
    print("=" * 60)
    print(alert_agent.get_log_summary(last_n=20))
    print(alert_agent.get_fault_summary())
    print()


def _print_summary(alert_agent: AlertAgent, env: Environment, elapsed: int):
    """Print a mid-run summary of system activity."""
    label = f"{elapsed}s elapsed" if elapsed > 0 else "periodic"
    print(f"\n{'─'*60}")
    print(f"  📊 Summary at {label} | Sim time: {env.get_sim_time()}")
    print(f"  Log entries: {len(alert_agent.event_log)}")
    print(f"  Fault registry: {len(alert_agent.fault_registry)} device(s) faulted")
    print(f"{'─'*60}\n")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Smart Campus Energy Monitor — SPADE agent simulation"
    )
    parser.add_argument("--monitor-jid",  default=DEFAULT_CREDS["monitor"]["jid"])
    parser.add_argument("--monitor-pwd",  default=DEFAULT_CREDS["monitor"]["pwd"])
    parser.add_argument("--decision-jid", default=DEFAULT_CREDS["decision"]["jid"])
    parser.add_argument("--decision-pwd", default=DEFAULT_CREDS["decision"]["pwd"])
    parser.add_argument("--alert-jid",    default=DEFAULT_CREDS["alert"]["jid"])
    parser.add_argument("--alert-pwd",    default=DEFAULT_CREDS["alert"]["pwd"])
    parser.add_argument("--duration",     type=int, default=SIM_DURATION,
                        help="Simulation duration in real seconds (0 = run forever)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    creds = {
        "monitor":  {"jid": args.monitor_jid,  "pwd": args.monitor_pwd},
        "decision": {"jid": args.decision_jid, "pwd": args.decision_pwd},
        "alert":    {"jid": args.alert_jid,    "pwd": args.alert_pwd},
    }
    spade.run(main(creds))
