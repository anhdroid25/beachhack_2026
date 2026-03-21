import time
from supabase import create_client

supabase = create_client("URL", "KEY")

def listen_to_auction():
    print("Mock Truck: Listening for price drops...")
    while True:
        res = supabase.table("auction").select("*").eq("status", "active").execute()
        if res.data:
            price = res.data[0]['current_price']
            print(f"Current Market Price: ${price}")
        time.sleep(5)

listen_to_auction()