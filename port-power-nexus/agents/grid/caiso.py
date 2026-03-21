import requests
import zipfile
import io
import pandas as pd
from datetime import datetime, timedelta

def fetch_actual_caiso_api(node="TH_SP15_GEN-APND"):
    """
    Fetches the latest Real-Time Market (RTM) Locational Marginal Price (LMP).
    Note: CAISO data is usually delayed by a few minutes.
    """
    base_url = "https://oasis.caiso.com/mrtu-oasis/SingleZip"
    
    now = datetime.now()
    start_str = (now - timedelta(hours=2)).strftime("%Y%m%dT%H:%M-0000")
    end_str = now.strftime("%Y%m%dT%H:%M-0000")

    params = {
        "queryname": "PRC_LMP",
        "startdatetime": start_str,
        "enddatetime": end_str,
        "version": 1,
        "market_run_id": "RTM",  
        "node": node,            
        "resultformat": 6       
    }

    try:
        response = requests.get(base_url, params=params, timeout=15)
        response.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            csv_filename = z.namelist()[0]
            with z.open(csv_filename) as f:
                df = pd.read_csv(f)

                lmp_df = df[df['LMP_TYPE'] == 'LMP'].sort_values(by='INTERVALSTARTTIME_GMT')
                
                if not lmp_df.empty:
                    latest_price = lmp_df.iloc[-1]['MW']
                    return float(latest_price)
                
        return None

    except Exception as e:
        print(f"Error fetching from CAISO: {e}")
        return None