from uagents import Agent, Context, Bureau
from shared.models import GridSignal, PowerBid, BidResponse
from shared.supabase_client import supabase
from agents.trucks.bidding import decide_bid
from datetime import datetime

TERMINAL_ADDRESS = "agent1q2dsyxc0g3482s3cewzss6vf4gakd2r8znask0gpmqrnvm0p5n0fy9gsulk"


def _soc_from_hub(truck_name: str, fallback: float) -> float:
    """Match Supabase `trucks.state_of_charge` (terminal updates while charging)."""
    r = (
        supabase.table("trucks")
        .select("state_of_charge")
        .eq("name", truck_name)
        .limit(1)
        .execute()
    )
    if r.data:
        return float(r.data[0]["state_of_charge"])
    return fallback


def stress_label(stress: float) -> str:
    if stress < 0.33:
        return "low"
    if stress < 0.66:
        return "medium"
    return "high"

# --- 3 trucks from different companies, each with private battery state ---
# Local agents: distinct ports, HTTP submit only (mailbox=False is the Agent default).
_truck_kw = dict(
    endpoint=["http://localhost:8000/submit"],
    network="testnet",
)
truck1 = Agent(name="amazon_truck", seed="amazon_truck_seed", port=8011, **_truck_kw)
truck2 = Agent(name="fedex_truck", seed="fedex_truck_seed", port=8012, **_truck_kw)
truck3 = Agent(name="ups_truck", seed="ups_truck_seed", port=8013, **_truck_kw)

# Private battery levels — not shared with competitors
amazon_battery = 20.0
fedex_battery = 55.0
ups_battery = 80.0


# ─────────────────────────── AMAZON ───────────────────────────

@truck1.on_message(model=GridSignal)
async def amazon_on_grid(ctx: Context, sender: str, signal: GridSignal):
    global amazon_battery
    amazon_battery = _soc_from_hub("amazon_truck", amazon_battery)
    result = decide_bid(amazon_battery, signal.current_price, stress_label(signal.grid_stress))
    bid = PowerBid(
        truck_id="amazon_truck",
        battery_level=amazon_battery,
        requested_kwh=50.0,
        bid_price=result["bid_price"],
        reasoning=result["reasoning"],
        timestamp=datetime.now()
    )
    ctx.logger.info(f"Amazon: bidding ${result['bid_price']:.2f}/kWh — {result['reasoning']}")
    await ctx.send(TERMINAL_ADDRESS, bid)

@truck1.on_message(model=BidResponse)
async def amazon_on_response(ctx: Context, sender: str, response: BidResponse):
    global amazon_battery
    if response.accepted:
        amazon_battery = _soc_from_hub("amazon_truck", amazon_battery)
        ctx.logger.info(
            f"Amazon: charging at bay {response.bay} — SOC {amazon_battery:.0f}% (hub)"
        )
    else:
        ctx.logger.info(f"Amazon: rejected, queue position {response.queue_position}")


# ─────────────────────────── FEDEX ───────────────────────────

@truck2.on_message(model=GridSignal)
async def fedex_on_grid(ctx: Context, sender: str, signal: GridSignal):
    global fedex_battery
    fedex_battery = _soc_from_hub("fedex_truck", fedex_battery)
    result = decide_bid(fedex_battery, signal.current_price, stress_label(signal.grid_stress))
    bid = PowerBid(
        truck_id="fedex_truck",
        battery_level=fedex_battery,
        requested_kwh=40.0,
        bid_price=result["bid_price"],
        reasoning=result["reasoning"],
        timestamp=datetime.now()
    )
    ctx.logger.info(f"FedEx: bidding ${result['bid_price']:.2f}/kWh — {result['reasoning']}")
    await ctx.send(TERMINAL_ADDRESS, bid)

@truck2.on_message(model=BidResponse)
async def fedex_on_response(ctx: Context, sender: str, response: BidResponse):
    global fedex_battery
    if response.accepted:
        fedex_battery = _soc_from_hub("fedex_truck", fedex_battery)
        ctx.logger.info(
            f"FedEx: charging at bay {response.bay} — SOC {fedex_battery:.0f}% (hub)"
        )
    else:
        ctx.logger.info(f"FedEx: rejected, queue position {response.queue_position}")


# ─────────────────────────── UPS ───────────────────────────

@truck3.on_message(model=GridSignal)
async def ups_on_grid(ctx: Context, sender: str, signal: GridSignal):
    global ups_battery
    ups_battery = _soc_from_hub("ups_truck", ups_battery)
    result = decide_bid(ups_battery, signal.current_price, stress_label(signal.grid_stress))
    bid = PowerBid(
        truck_id="ups_truck",
        battery_level=ups_battery,
        requested_kwh=30.0,
        bid_price=result["bid_price"],
        reasoning=result["reasoning"],
        timestamp=datetime.now()
    )
    ctx.logger.info(f"UPS: bidding ${result['bid_price']:.2f}/kWh — {result['reasoning']}")
    await ctx.send(TERMINAL_ADDRESS, bid)

@truck3.on_message(model=BidResponse)
async def ups_on_response(ctx: Context, sender: str, response: BidResponse):
    global ups_battery
    if response.accepted:
        ups_battery = _soc_from_hub("ups_truck", ups_battery)
        ctx.logger.info(
            f"UPS: charging at bay {response.bay} — SOC {ups_battery:.0f}% (hub)"
        )
    else:
        ctx.logger.info(f"UPS: rejected, queue position {response.queue_position}")


# ─────────────────────────── RUN ───────────────────────────

if __name__ == "__main__":
    bureau = Bureau()
    bureau.add(truck1)
    bureau.add(truck2)
    bureau.add(truck3)
    bureau.run()
