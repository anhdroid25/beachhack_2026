# seed.py — run once to populate all tables
import os
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime, timezone
import uuid

load_dotenv()

supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# --- Fixed UUIDs so foreign keys line up cleanly ---
TRUCK_IDS = {
    "Truck_01": str(uuid.uuid4()),
    "Truck_02": str(uuid.uuid4()),
    "Truck_03": str(uuid.uuid4()),
}

BAY_IDS = {
    "Bay A1": str(uuid.uuid4()),
    "Bay A2": str(uuid.uuid4()),
    "Bay A3": str(uuid.uuid4()),
}

AUCTION_ID = "active_auction_1"

def seed_bays():
    rows = [
        {"id": BAY_IDS["Bay A1"], "name": "Bay A1", "status": "available", "assigned_truck_id": None, "locked_at": None},
        {"id": BAY_IDS["Bay A2"], "name": "Bay A2", "status": "available", "assigned_truck_id": None, "locked_at": None},
        {"id": BAY_IDS["Bay A3"], "name": "Bay A3", "status": "available", "assigned_truck_id": None, "locked_at": None},
    ]
    supabase.table("bays").upsert(rows).execute()
    print("✅ Seeded bays")

def seed_trucks():
    rows = [
        {
            "id": TRUCK_IDS["Truck_01"],
            "name": "Truck_01",
            "state_of_charge": 18,        # critically low — will bid aggressively
            "distance_to_port": 3,
            "status": "bidding",
            "bay_id": None,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        },
        {
            "id": TRUCK_IDS["Truck_02"],
            "name": "Truck_02",
            "state_of_charge": 45,        # moderate — will wait for better price
            "distance_to_port": 12,
            "status": "idle",
            "bay_id": None,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        },
        {
            "id": TRUCK_IDS["Truck_03"],
            "name": "Truck_03",
            "state_of_charge": 72,        # comfortable — holding out
            "distance_to_port": 28,
            "status": "idle",
            "bay_id": None,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        },
    ]
    supabase.table("trucks").upsert(rows).execute()
    print("✅ Seeded trucks")

def seed_auction_state():
    rows = [
        {
            "id": AUCTION_ID,
            "status": "active",
            "current_price": 98.50,       # grid agent will take over from here
            "renewable_pct": 62,
            "grid_stress": 0.44,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
    ]
    supabase.table("auction_state").upsert(rows).execute()
    print("✅ Seeded auction_state")

def seed_power_bids():
    bid_id = str(uuid.uuid4())
    rows = [
        {
            "id": bid_id,
            "truck_id": TRUCK_IDS["Truck_01"],
            "battery_level": 18,
            "requested_kwh": 150,
            "bid_price": 91.20,
            "reasoning": "Battery critically low at 18%. Cannot reach next depot without charge. Accepting current price despite high grid stress.",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    supabase.table("power_bids").upsert(rows).execute()
    print("✅ Seeded power_bids")
    return bid_id   # needed for bid_responses FK

def seed_bid_responses(bid_id: str):
    rows = [
        {
            "id": str(uuid.uuid4()),
            "bid_id": bid_id,
            "accepted": True,
            "bay_id": BAY_IDS["Bay A1"],
            "price_confirmed": 91.20,
            "queue_position": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    supabase.table("bid_responses").upsert(rows).execute()
    print("✅ Seeded bid_responses")

if __name__ == "__main__":
    print("🌱 Seeding Port-Power Nexus database...\n")
    seed_bays()
    seed_trucks()
    seed_auction_state()
    bid_id = seed_power_bids()
    seed_bid_responses(bid_id)
    print("\n🚀 Done. Grid agent can take over auction_state now.")