import os
import requests
import zipfile
import io
import pandas as pd
from datetime import datetime, timezone, timedelta

def fetch_actual_caiso_api(query="PRC_INTVL_LMP", node=None):
    """
    Fetches Real-Time Market (RTM) price data from CAISO OASIS API.
    
    Args:
        query (str): Query name—typically "PRC_INTVL_LMP" for interval LMP prices
        node (str): CAISO node identifier (e.g., "TH_SP15_GEN-APND")
    
    Returns:
        float: Most recent interval LMP price in $/MWh, or None on error
    
    Note:
        - CAISO has a ~15–20 min publication lag
        - Queries data from 2 hours ago to 1 hour ago (safe historical window)
        - Format/Version: v1 with YYYYMMDDTHHMM-0000 timestamp (no colons/seconds)
    """
    if node is None:
        node = os.getenv("CAISO_NODE", "TH_SP15_GEN-APND")
    
    base_url = "https://oasis.caiso.com/mrtu-oasis/SingleZip"
    
    # Use UTC timezone-aware datetime
    now = datetime.now(timezone.utc)
    
    # CAISO data lags ~15–20 min; query 2hrs–1hr ago for guaranteed availability
    start_dt = now - timedelta(hours=2)
    end_dt = now - timedelta(hours=1)
    
    # Format: YYYYMMDDTHHMM-0000 (ISO 8601 with fixed UTC offset, NO colons in time portion)
    start_str = start_dt.strftime("%Y%m%dT%H%M-0000")  # e.g., "20260321T1900-0000"
    end_str = end_dt.strftime("%Y%m%dT%H%M-0000")      # e.g., "20260321T2000-0000"
    
    # Robust parameter dictionary for proper URL encoding
    params = {
        "queryname": query,
        "startdatetime": start_str,
        "enddatetime": end_str,
        "version": 1,
        "market_run_id": "RTM",
        "node": node,
        "resultformat": 6  # Zip format
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=15)
        response.raise_for_status()
        
        # Parse ZIP response
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            csv_name = z.namelist()[0]
            with z.open(csv_name) as f:
                df = pd.read_csv(f)
                
                # Debug: Log column names on first call
                print(f"   ℹ️  CAISO columns: {df.columns.tolist()}")
                
                # Filter for LMP rows only (exclude Congestion & Loss components)
                df = df[df['LMP_TYPE'] == 'LMP'].sort_values('INTERVALSTARTTIME_GMT')
                
                if df.empty:
                    print("   ⚠️ No LMP rows found after filtering")
                    return None
                
                # Extract latest interval price value
                latest_row = df.iloc[-1]
                price_value = latest_row.get('VALUE', latest_row.get('MW'))
                
                if price_value is None:
                    print(f"   ⚠️ Price column not found. Available: {df.columns.tolist()}")
                    return None
                
                return float(price_value)
    
    except zipfile.BadZipFile:
        print(f"   ⚠️ CAISO returned non-ZIP (likely XML error response)")
        print(f"   Response preview: {response.text[:300] if response else 'No response'}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"   ⚠️ HTTP Error: {e}")
        return None
    except KeyError as e:
        print(f"   ⚠️ Missing expected CSV column: {e}")
        return None
    except Exception as e:
        print(f"   ⚠️ Unexpected error fetching CAISO data: {e}")
        return None