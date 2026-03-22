"""Run all agents in one Bureau for local development.

Agents in the same Bureau communicate directly without needing
the Fetch.ai Almanac or funded wallets.

Includes the Logistics orchestrator (ASI:One Chat Protocol), which uses
``mailbox=True`` on its own port; swarm agents use HTTP submit (``mailbox=False``).
The Bureau keeps the orchestrator’s mailbox endpoints when adding it.

Agentverse Local Inspector does not support Bureaus. For Inspector + full swarm,
use two terminals: `run_swarm_bureau.py` then `run_orchestrator_for_inspector.py`.
"""
from pathlib import Path

from dotenv import load_dotenv

_repo_root = Path(__file__).resolve().parents[1]
load_dotenv(_repo_root / ".env", override=True)

from uagents import Bureau
from agents.grid.agent import grid_agent
from agents.orchestrator.agent import orchestrator_agent
from agents.terminal.agent import terminal
from agents.trucks.agent import truck1, truck2, truck3

bureau = Bureau(port=8000, endpoint="http://localhost:8000/submit")
bureau.add(orchestrator_agent)
bureau.add(grid_agent)
bureau.add(truck1)
bureau.add(truck2)
bureau.add(truck3)
bureau.add(terminal)
bureau.run()
