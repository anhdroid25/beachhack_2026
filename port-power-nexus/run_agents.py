"""All swarm agents + orchestrator in one Bureau (same as ``run_all.py`` pattern).

Prefer ``run_all.py`` or ``run_swarm_bureau.py`` + ``run_orchestrator_for_inspector.py``.
"""
from uagents import Bureau

from agents.grid.agent import grid_agent
from agents.orchestrator.agent import orchestrator_agent
from agents.terminal.agent import terminal
from agents.trucks.agent import truck1, truck2, truck3


def main() -> None:
    bureau = Bureau(port=8000, endpoint="http://localhost:8000/submit")
    bureau.add(orchestrator_agent)
    bureau.add(grid_agent)
    bureau.add(truck1)
    bureau.add(truck2)
    bureau.add(truck3)
    bureau.add(terminal)
    bureau.run()


if __name__ == "__main__":
    main()
