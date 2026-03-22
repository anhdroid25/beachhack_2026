from datetime import datetime

from uagents import Agent, Context

from shared.models import BidResponse, PowerBid, TruckStatusRequest, TruckStatusResponse
from shared.supabase_client import supabase
from agents.terminal.bay_manager import (
    DEMO_CHARGE_TICK_S,
    finalize_trucks_after_port,
    get_available_bay,
    lock_bay,
    log_event,
    save_bid,
    save_bid_response,
    tick_charging_sessions,
    update_truck_status,
)

# Local agent: own port + HTTP submit; do not use mailbox=True (orchestrator only).
terminal = Agent(
    name="terminal",
    seed="terminal_seed",
    port=8010,
    endpoint=["http://localhost:8010/submit"],
    network="testnet",
)

# Tracks bid queue position across rounds
bid_queue = []

# Orchestrator sends Truck_01 / aliases; DB uses amazon_truck, etc.
_TRUCK_ID_TO_DB_NAME = {
    "Truck_01": "amazon_truck",
    "Truck_02": "fedex_truck",
    "Truck_03": "ups_truck",
}


def _db_name_for_truck_id(truck_id: str) -> str | None:
    if truck_id in _TRUCK_ID_TO_DB_NAME:
        return _TRUCK_ID_TO_DB_NAME[truck_id]
    if truck_id in ("amazon_truck", "fedex_truck", "ups_truck"):
        return truck_id
    return None


@terminal.on_message(model=TruckStatusRequest)
async def handle_truck_status_request(
    ctx: Context, sender: str, msg: TruckStatusRequest
) -> None:
    db_name = _db_name_for_truck_id(msg.truck_id)
    if not db_name:
        await ctx.send(
            msg.reply_to,
            TruckStatusResponse(
                request_id=msg.request_id,
                truck_id=msg.truck_id,
                truck_status="unknown_truck_id",
                state_of_charge=None,
                distance_to_port=None,
                bay=None,
                timestamp=datetime.utcnow(),
            ),
        )
        return

    r = (
        supabase.table("trucks")
        .select("status,state_of_charge,distance_to_port,bay_id")
        .eq("name", db_name)
        .limit(1)
        .execute()
    )
    if not r.data:
        await ctx.send(
            msg.reply_to,
            TruckStatusResponse(
                request_id=msg.request_id,
                truck_id=msg.truck_id,
                truck_status="not_found",
                state_of_charge=None,
                distance_to_port=None,
                bay=None,
                timestamp=datetime.utcnow(),
            ),
        )
        return

    row = r.data[0]
    bay_name: str | None = None
    bid = row.get("bay_id")
    if bid:
        br = supabase.table("bays").select("name").eq("id", bid).limit(1).execute()
        if br.data:
            bay_name = br.data[0].get("name")

    soc = row.get("state_of_charge")
    dist = row.get("distance_to_port")

    await ctx.send(
        msg.reply_to,
        TruckStatusResponse(
            request_id=msg.request_id,
            truck_id=msg.truck_id,
            truck_status=str(row.get("status") or "unknown"),
            state_of_charge=float(soc) if soc is not None else None,
            distance_to_port=float(dist) if dist is not None else None,
            bay=bay_name,
            timestamp=datetime.utcnow(),
        ),
    )


@terminal.on_message(model=PowerBid)
async def handle_bid(ctx: Context, sender: str, bid: PowerBid):
    ctx.logger.info(f"Terminal received bid from {bid.truck_id}: ${bid.bid_price}/kWh")
    reason = (bid.reasoning or "").strip().replace("\n", " ")
    if len(reason) > 220:
        reason = reason[:217] + "..."
    log_event(
        "bid",
        f"BID {bid.truck_id} ${bid.bid_price:.2f}/kWh · batt {bid.battery_level:.0f}% · {reason}",
    )

    # Save bid to Supabase
    bid_id = save_bid(
        truck_name=bid.truck_id,
        battery_level=bid.battery_level,
        requested_kwh=bid.requested_kwh,
        bid_price=bid.bid_price,
        reasoning=bid.reasoning
    )

    # Track queue position
    if bid.truck_id not in bid_queue:
        bid_queue.append(bid.truck_id)
    queue_position = bid_queue.index(bid.truck_id) + 1

    # Try to find and lock an available bay
    bay = get_available_bay()

    if bay:
        locked = lock_bay(bay["id"], bid.truck_id)

        if locked:
            # Winner — bay secured
            update_truck_status(
                bid.truck_id,
                "charging",
                bay["id"],
                state_of_charge=int(bid.battery_level),
            )
            save_bid_response(bid_id, True, bay["id"], bid.bid_price, queue_position)

            response = BidResponse(
                accepted=True,
                bay=bay["name"],
                price_confirmed=bid.bid_price,
                queue_position=queue_position
            )
            ctx.logger.info(f"Terminal: {bid.truck_id} won bay {bay['name']}")
            log_event("win", f"terminal → {bid.truck_id}: ACCEPTED bay={bay['name']} at ${bid.bid_price:.2f}/kWh")

            # Ledger transaction — optional demo (needs funded testnet wallet)
            try:
                await ctx.ledger.send_tokens(
                    destination=terminal.wallet.address(),
                    amount=int(bid.bid_price * 100),  # uFET scale
                    denom="atestfet",
                    sender=terminal.wallet,
                    memo=f"charge-{bid.truck_id}-{bay['name']}",
                )
                ctx.logger.info(f"Terminal: ledger tx sent for {bid.truck_id}")
            except Exception as e:
                ctx.logger.warning(f"Terminal: ledger tx failed — {e}")
        else:
            # Bay was locked by another truck in a race
            save_bid_response(bid_id, False, None, bid.bid_price, queue_position)
            response = BidResponse(
                accepted=False,
                bay=None,
                price_confirmed=bid.bid_price,
                queue_position=queue_position
            )
            ctx.logger.info(f"Terminal: {bid.truck_id} lost — bay taken")
            log_event("bid", f"terminal → {bid.truck_id}: REJECTED — bay taken by another truck")
    else:
        # No bays available
        save_bid_response(bid_id, False, None, bid.bid_price, queue_position)
        response = BidResponse(
            accepted=False,
            bay=None,
            price_confirmed=bid.bid_price,
            queue_position=queue_position
        )
        ctx.logger.info(f"Terminal: {bid.truck_id} rejected — no bays available")
        log_event("bid", f"terminal → {bid.truck_id}: REJECTED — no bays available")

    await ctx.send(sender, response)


@terminal.on_interval(period=DEMO_CHARGE_TICK_S)
async def demo_charging_tick(ctx: Context) -> None:
    try:
        tick_charging_sessions()
        finalize_trucks_after_port()
    except Exception as e:
        ctx.logger.warning(f"Terminal: charging tick failed — {e}")


if __name__ == "__main__":
    print(f"Terminal agent address: {terminal.address}")
    terminal.run()
