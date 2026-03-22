"""Run grid + trucks + terminal in one Bureau (port 8000) — no orchestrator.

Swarm agents use **HTTP submit** (``mailbox=False``); they share the Bureau listener
on **:8000**. Do **not** run another agent on 8000 while this is running.

**Orchestrator (separate terminal):** uses ``mailbox=True`` and its **own** port
(default **8002** via ``ORCHESTRATOR_INSPECTOR_PORT``) for Inspector + mailbox.

Use with `run_orchestrator_for_inspector.py`:

  Terminal 1: python run_swarm_bureau.py
  Terminal 2: python run_orchestrator_for_inspector.py

Do not run `run_all.py` at the same time (port 8000 conflict).
"""
from pathlib import Path

from dotenv import load_dotenv

_repo_root = Path(__file__).resolve().parents[1]
load_dotenv(_repo_root / ".env", override=True)

from uagents import Bureau
from agents.grid.agent import grid_agent
from agents.terminal.agent import terminal
from agents.trucks.agent import truck1, truck2, truck3

bureau = Bureau(port=8000, endpoint="http://localhost:8000/submit")
bureau.add(grid_agent)
bureau.add(truck1)
bureau.add(truck2)
bureau.add(truck3)
bureau.add(terminal)
bureau.run()
