import os
import asyncio
import requests
import uuid
from datetime import datetime, timezone

import shared.env_loader  # noqa: F401 — repo root .env

from supabase import create_client, Client
from uagents import Agent, Context, Model
from uagents.setup import fund_agent_if_low
from shared.models import (
    GridSignal,
    AgentErrorResponse,
    AuctionStarted,
    FinalAssignmentResponse,
    StartAuctionRequest,
)

SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["SUPABASE_KEY"]

# Truck agent addresses — fill in after each truck agent is registered
TRUCK_AGENT_ADDRESSES: list[str] = os.environ.get(
    "TRUCK_AGENT_ADDRESSES", ""
).split(",")

# GridStatus API — https://api.gridstatus.io/v1
GRIDSTATUS_API_KEY: str = os.environ.get("GRIDSTATUS_API_KEY", "")
GRIDSTATUS_BASE_URL = "https://api.gridstatus.io/v1"

# Dutch Auction parameters
AUCTION_START_PRICE: float = float(os.environ.get("AUCTION_START_PRICE", "0.35"))   # $/kWh
AUCTION_MIN_PRICE: float   = float(os.environ.get("AUCTION_MIN_PRICE",   "0.08"))   # $/kWh
AUCTION_PRICE_STEP: float  = float(os.environ.get("AUCTION_PRICE_STEP",  "0.01"))   # drop per tick
AUCTION_TICK_SECONDS: int  = int(os.environ.get("AUCTION_TICK_SECONDS",  "5"))
GRID_AGENT_PORT: int = int(os.environ.get("GRID_AGENT_PORT", "8001"))
# Swarm / local agents: HTTP submit only (not mailbox). Only the orchestrator uses mailbox=True.
GRID_AGENT_USE_MAILBOX: bool = os.environ.get(
    "GRID_AGENT_USE_MAILBOX", "false"
).lower() in {"1", "true", "yes", "on"}
GRID_AGENT_ENDPOINT: str | None = None if GRID_AGENT_USE_MAILBOX else (
    os.environ.get("GRID_AGENT_ENDPOINT")
    or f"http://127.0.0.1:{GRID_AGENT_PORT}/submit"
)


# GridSignal imported from shared.models — both sides must use the same class.

class AuctionComplete(Model):
    """Sent from Grid Agent → Truck Agents when the auction ends."""
    auction_id: str
    reason:     str   # "price_floor_reached" | "bid_accepted"



def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def upsert_auction(sb: Client, auction_id: str, payload: dict) -> None:
    """Insert or update the single active auction row."""
    sb.table("auction_state").upsert({"id": auction_id, **payload}).execute()


def log_event(sb: Client, event_type: str, message: str) -> None:
    sb.table("events").insert({
        "type":       event_type,
        "message":    message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()



def _gridstatus_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if GRIDSTATUS_API_KEY:
        headers["x-api-key"] = GRIDSTATUS_API_KEY
    return headers


def fetch_caiso_fuel_mix() -> dict:
    """
    Returns the latest CAISO fuel mix snapshot from GridStatus.
    Endpoint: GET /datasets/caiso_fuel_mix/latest
    Falls back to neutral defaults if the request fails.
    """
    try:
        url = f"{GRIDSTATUS_BASE_URL}/datasets/caiso_fuel_mix/query"
        resp = requests.get(
            url,
            headers=_gridstatus_headers(),
            params={"limit": 1, "order_by": "interval_start_utc desc"},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()

        # GridStatus wraps results in {"data": [...]}
        rows = data.get("data", [])
        if not rows:
            raise ValueError("Empty fuel mix response")

        row = rows[0]
        # Sum renewable sources: solar, wind, geothermal, small_hydro, biomass, biogas
        renewable_keys = ["solar", "wind", "geothermal", "small_hydro", "biomass", "biogas"]
        all_keys = ["solar", "wind", "geothermal", "biomass", "biogas", "small_hydro", "coal", "nuclear", "natural_gas", "large_hydro", "batteries", "imports", "other"]
        total_mw  = sum(row.get(k, 0) or 0 for k in all_keys) or 1  # avoid div/0
        renew_mw  = sum(row.get(k, 0) or 0 for k in renewable_keys)
        renewable_pct = round((renew_mw / total_mw) * 100, 1)

        return {
            "renewable_pct": min(renewable_pct, 100.0),
            "ca_iso_zone":   "CAISO",
            "raw_row":       row,
        }

    except Exception as exc:  # noqa: BLE001
        print(f"[GridAgent] GridStatus fuel-mix fetch failed: {exc} — using defaults")
        return {"renewable_pct": 25.0, "ca_iso_zone": "CAISO", "raw_row": {}}


def fetch_caiso_load() -> dict:
    """
    Returns the latest CAISO system load to derive grid_stress (0.0–1.0).
    Endpoint: GET /datasets/caiso_load/latest
    Falls back to 0.5 if the request fails.
    """
    # Rough capacity benchmark for CAISO peak (MW)
    CAISO_PEAK_CAPACITY_MW = 52_000

    try:
        url = f"{GRIDSTATUS_BASE_URL}/datasets/caiso_load/query"
        resp = requests.get(
            url,
            headers=_gridstatus_headers(),
            params={"limit": 1, "order_by": "interval_start_utc desc"},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()

        rows = data.get("data", [])
        if not rows:
            raise ValueError("Empty load response")

        load_mw = rows[0].get("load", 0) or 0
        stress  = round(min(load_mw / CAISO_PEAK_CAPACITY_MW, 1.0), 3)
        return {"grid_stress": stress, "load_mw": load_mw}

    except Exception as exc:  # noqa: BLE001
        print(f"[GridAgent] GridStatus load fetch failed: {exc} — using defaults")
        return {"grid_stress": 0.5, "load_mw": 0}


_grid_cache: dict = {}
_grid_cache_time: float = 0.0
GRID_CACHE_SECONDS = 30

def fetch_grid_data() -> dict:
    """Merge fuel-mix + load into a single snapshot dict. Cached every 30 seconds."""
    import time
    global _grid_cache, _grid_cache_time
    if _grid_cache and (time.time() - _grid_cache_time) < GRID_CACHE_SECONDS:
        return _grid_cache
    fuel  = fetch_caiso_fuel_mix()
    load  = fetch_caiso_load()
    _grid_cache = {
        "renewable_pct": fuel["renewable_pct"],
        "grid_stress":   load["grid_stress"],
        "ca_iso_zone":   fuel["ca_iso_zone"],
        "load_mw":       load["load_mw"],
    }
    _grid_cache_time = time.time()
    return _grid_cache


grid_agent = Agent(
    name     = "grid_agent",
    seed     = os.environ.get("GRID_AGENT_SEED", "grid_agent_secret_seed"),
    port     = GRID_AGENT_PORT,
    endpoint = GRID_AGENT_ENDPOINT,
    mailbox  = GRID_AGENT_USE_MAILBOX,
    # Match orchestrator (testnet) so Almanac contract registration can use testnet FET.
    network  = "testnet",
)

fund_agent_if_low(grid_agent.wallet.address())



class AuctionState:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.auction_id:    str   = ""
        self.current_price: float = AUCTION_START_PRICE
        self.active:        bool  = False
        self.tick_count:    int   = 0
        self.request_id:    str   = ""
        self.reply_to:      str   = ""
        self.target_truck:  str   = ""
        self.requested_goal: str | None = None

    def drop_price(self) -> None:
        self.current_price = round(
            max(self.current_price - AUCTION_PRICE_STEP, AUCTION_MIN_PRICE), 4
        )
        self.tick_count += 1

    @property
    def at_floor(self) -> bool:
        return self.current_price <= AUCTION_MIN_PRICE


_state = AuctionState()

# Stable row id for “no auction yet” — TopBar reads latest by `started_at`; orchestrator starts real auctions with new UUIDs.
IDLE_AUCTION_ROW_ID = "grid_idle"


@grid_agent.on_event("startup")
async def on_startup(ctx: Context) -> None:
    """Idle until the orchestrator sends `StartAuctionRequest` (user prompt via ASI:One / chat)."""
    sb = get_supabase()

    _state.reset()
    _state.auction_id = IDLE_AUCTION_ROW_ID
    _state.active = False

    upsert_auction(sb, IDLE_AUCTION_ROW_ID, {
        "current_price": AUCTION_START_PRICE,
        "start_price":   AUCTION_START_PRICE,
        "min_price":     AUCTION_MIN_PRICE,
        "renewable_pct": 0.0,
        "grid_stress":   0.0,
        "status":        "idle",
        "started_at":    datetime.now(timezone.utc).isoformat(),
    })
    log_event(
        sb,
        "signal",
        "Grid idle — waiting for orchestrator to start an auction (user request).",
    )

    ctx.logger.info(
        f"[GridAgent] Idle (no auction). address={ctx.agent.address} "
        f"mailbox={GRID_AGENT_USE_MAILBOX} endpoint={GRID_AGENT_ENDPOINT}"
    )


@grid_agent.on_message(model=StartAuctionRequest)
async def on_start_auction_request(ctx: Context, sender: str, msg: StartAuctionRequest) -> None:
    sb = get_supabase()

    _state.reset()
    _state.auction_id = str(uuid.uuid4())
    _state.active = True
    _state.request_id = msg.request_id
    _state.reply_to = msg.reply_to
    _state.target_truck = msg.truck_id
    _state.requested_goal = msg.requested_goal

    upsert_auction(sb, _state.auction_id, {
        "current_price": AUCTION_START_PRICE,
        "start_price": AUCTION_START_PRICE,
        "min_price": AUCTION_MIN_PRICE,
        "renewable_pct": 0.0,
        "grid_stress": 0.0,
        "status": "active",
        "started_at": datetime.now(timezone.utc).isoformat(),
    })
    log_event(
        sb,
        "auction_start",
        f"Orchestrator requested auction {_state.auction_id} for {msg.truck_id}",
    )

    ctx.logger.info(
        f"[GridAgent] Received StartAuctionRequest request_id={msg.request_id} "
        f"truck={msg.truck_id} sender={sender}"
    )

    await ctx.send(
        msg.reply_to,
        AuctionStarted(
            request_id=msg.request_id,
            truck_id=msg.truck_id,
            status="accepted",
            note=(
                f"The Dutch auction is live at ${AUCTION_START_PRICE:.2f}/kWh and "
                f"broadcasting to {len([a for a in TRUCK_AGENT_ADDRESSES if a.strip()])} truck agents."
            ),
            timestamp=datetime.now(timezone.utc),
        ),
    )


@grid_agent.on_interval(period=AUCTION_TICK_SECONDS)
async def auction_tick(ctx: Context) -> None:
    if not _state.active:
        return

    # 1. Pull live grid data from GridStatus
    grid = fetch_grid_data()

    # 2. Drop price
    _state.drop_price()

    now_iso = datetime.now(timezone.utc).isoformat()

    # 3. Build the signal
    signal = GridSignal(
        auction_id    = _state.auction_id,
        current_price = _state.current_price,
        start_price   = AUCTION_START_PRICE,
        min_price     = AUCTION_MIN_PRICE,
        renewable_pct = grid["renewable_pct"],
        grid_stress   = grid["grid_stress"],
        ca_iso_zone   = grid["ca_iso_zone"],
        timestamp     = now_iso,
    )

    ctx.logger.info(
        f"[GridAgent] Tick #{_state.tick_count} | "
        f"price=${_state.current_price:.4f} | "
        f"renewable={grid['renewable_pct']}% | "
        f"stress={grid['grid_stress']}"
    )

    # 4. Update Supabase (frontend reads this)
    sb = get_supabase()
    upsert_auction(sb, _state.auction_id, {
        "current_price": _state.current_price,
        "renewable_pct": grid["renewable_pct"],
        "grid_stress":   grid["grid_stress"],
        "status":        "active",
    })

    # 5. Broadcast to all truck agents (throttle feed: every 3rd tick still shows grid↔swarm rhythm)
    if _state.tick_count % 3 == 0:
        log_event(
            sb,
            "signal",
            f"grid_agent → trucks: price=${_state.current_price:.2f}/kWh | "
            f"renewable={grid['renewable_pct']}% | stress={grid['grid_stress']:.2f}",
        )
    for addr in TRUCK_AGENT_ADDRESSES:
        addr = addr.strip()
        if addr:
            await ctx.send(addr, signal)

    # 6. End auction if price has hit the floor
    if _state.at_floor:
        await _end_auction(ctx, reason="price_floor_reached")



class BidAccepted(Model):
    """Terminal Agent → Grid Agent: a truck won the auction."""
    auction_id: str
    truck_id:   str
    bay_id:     str
    price_paid: float


@grid_agent.on_message(model=BidAccepted)
async def on_bid_accepted(ctx: Context, sender: str, msg: BidAccepted) -> None:
    if msg.auction_id != _state.auction_id:
        ctx.logger.warning(f"[GridAgent] Stale BidAccepted for auction {msg.auction_id} — ignoring")
        return

    ctx.logger.info(
        f"[GridAgent] Bid accepted! truck={msg.truck_id} bay={msg.bay_id} "
        f"price=${msg.price_paid:.4f}"
    )

    sb = get_supabase()
    log_event(
        sb,
        "win",
        f"Truck {msg.truck_id} won bay {msg.bay_id} at ${msg.price_paid:.4f}/kWh",
    )

    if _state.reply_to and _state.request_id:
        await ctx.send(
            _state.reply_to,
            FinalAssignmentResponse(
                request_id=_state.request_id,
                truck_id=msg.truck_id,
                status="completed",
                decision_summary=(
                    f"{msg.truck_id} won the charging auction after the price dropped "
                    "into its bidding threshold."
                ),
                bay=msg.bay_id,
                price=msg.price_paid,
                tx_hash=None,
                timestamp=datetime.now(timezone.utc),
            ),
        )

    await _end_auction(ctx, reason="bid_accepted")


async def _end_auction(ctx: Context, reason: str) -> None:
    """Mark auction complete, update Supabase, notify all trucks."""
    if not _state.active:
        return

    _state.active = False

    sb = get_supabase()
    upsert_auction(sb, _state.auction_id, {"status": "complete"})
    log_event(sb, "auction_start", f"Auction {_state.auction_id} ended: {reason}")

    complete_msg = AuctionComplete(auction_id=_state.auction_id, reason=reason)
    for addr in TRUCK_AGENT_ADDRESSES:
        addr = addr.strip()
        if addr:
            await ctx.send(addr, complete_msg)

    if reason == "price_floor_reached" and _state.reply_to and _state.request_id:
        await ctx.send(
            _state.reply_to,
            AgentErrorResponse(
                request_id=_state.request_id,
                source_agent="grid_agent",
                error_message=(
                    f"The auction for {_state.target_truck or 'the requested truck'} "
                    "reached the price floor before any winning bid was accepted."
                ),
                timestamp=datetime.now(timezone.utc),
            ),
        )

    ctx.logger.info(f"[GridAgent] Auction {_state.auction_id} ended — {reason}")


if __name__ == "__main__":
    grid_agent.run()
