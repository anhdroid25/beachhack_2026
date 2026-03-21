import os
import time
import random
from caiso import fetch_actual_caiso_api
from supabase import create_client, Client
from dotenv import load_dotenv


load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

MOCK_MODE = True
CURRENT_PRICE = 100.0

def get_caiso_price():
    """Fetches real or mock price data."""
    global CURRENT_PRICE
    if MOCK_MODE:
        CURRENT_PRICE -= random.uniform(-0.5, 1.5) 
        return round(CURRENT_PRICE, 2)
    else:
        return fetch_actual_caiso_api()

def update_auction_state(price):
    """Updates Supabase and handles the 'broadcast' logic."""
    try:
        data, count = supabase.table("auction_state") \
            .update({"current_price": price, "last_updated": "now()"}) \
            .eq("id", "active_auction_1") \
            .execute()
        print(f"Updated Supabase: ${price}")
    except Exception as e:
        print(f"Supabase Error: {e}")

def run_agent():
    print("Grid Agent Started...")
    while True:
        start_time = time.time()
        
        price = get_caiso_price()
        
        update_auction_state(price)
        
        elapsed = time.time() - start_time
        sleep_time = max(0, 5.0 - elapsed)
        time.sleep(sleep_time)

if __name__ == "__main__":
    run_agent()