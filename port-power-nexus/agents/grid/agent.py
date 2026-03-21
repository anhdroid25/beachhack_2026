import os
import time
import random
from datetime import datetime, timezone, timedelta
from caiso import fetch_actual_caiso_api
from supabase import create_client, Client
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

AUCTION_ID = "active_auction_1" 
UNIT = "$/MWh" 
MOCK_MODE = False  
CAISO_NODE = os.getenv("CAISO_NODE", "TH_SP15_GEN-APND")

# Global state for price tracking
current_base_price = 100.0
last_caiso_fetch = datetime(1970, 1, 1, tzinfo=timezone.utc)  # Timezone-aware epoch

def get_grid_metrics():
    """Aggregates CAISO data, Dutch Auction logic, and display time."""
    global current_base_price, last_caiso_fetch
    
    now_utc = datetime.now(timezone.utc)
    
    # Fetch real data every 5 minutes to stay within CAISO rate limits
    if not MOCK_MODE and (now_utc - last_caiso_fetch).total_seconds() > 300:
        new_price = fetch_actual_caiso_api(node=CAISO_NODE)
        if new_price is not None:
            current_base_price = new_price
            last_caiso_fetch = now_utc

    # Dutch Auction local decay logic: drop price by $0.10 every second
    time_diff = (now_utc - last_caiso_fetch).total_seconds()
    adjusted_price = max(20.0, current_base_price - (time_diff * 0.1))

    return {
        "price": round(adjusted_price, 2),
        "unit": UNIT,
        "time": datetime.now().strftime("%I:%M:%S %p"),
        "renewable_pct": random.randint(45, 75),
        "grid_stress": round(random.uniform(0.2, 0.6), 2)
    }

def broadcast_to_swarm(metrics):
    """Updates the Supabase auction_state table[cite: 12, 106]."""
    try:
        supabase.table("auction_state").update({
            "current_price": metrics["price"],
            "renewable_pct": metrics["renewable_pct"],
            "grid_stress": metrics["grid_stress"],
            "last_updated": "now()"
        }).eq("id", AUCTION_ID).execute()

        # Final requested terminal display
        print(f"[{metrics['time']}] ⚡ GRID BROADCAST")
        print(f"      Market Price: {metrics['price']} {metrics['unit']}")
        print(f"      Renewables:   {metrics['renewable_pct']}%  |  Stress: {metrics['grid_stress']}")
        print("-" * 40)

    except Exception as e:
        print(f"[{metrics['time']}] ❌ Database Sync Error: {e}")

def run_agent():
    print(f"--- Port-Power Nexus: Grid Agent Active ---")
    print(f"Broadcasting to '{AUCTION_ID}' every 5 seconds...\n")
    
    while True:
        start_tick = time.time()
        
        metrics = get_grid_metrics()
        broadcast_to_swarm(metrics)
        
        # maintain 5-second interval 
        elapsed = time.time() - start_tick
        time.sleep(max(0, 5.0 - elapsed))

if __name__ == "__main__":
    run_agent()