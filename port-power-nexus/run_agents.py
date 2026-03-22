from uagents import Bureau

from agents.orchestrator.agent import orchestrator_agent
from agents.trucks.agent import truck1, truck2, truck3, truck4, truck5


def main() -> None:
    bureau = Bureau()
    bureau.add(orchestrator_agent)
    bureau.add(truck1)
    bureau.add(truck2)
    bureau.add(truck3)
    bureau.add(truck4)
    bureau.add(truck5)
    bureau.run()


if __name__ == "__main__":
    main()
