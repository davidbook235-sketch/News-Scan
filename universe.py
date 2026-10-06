"""Nifty LargeMidcap 250 list: NSE se download, fail ho to universe.csv use hota hai."""
import io, requests, pandas as pd
URL = "https://www.niftyindices.com/IndexConstituent/ind_niftylargemidcap250list.csv"

def load():
    try:
        r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        if len(df) > 100: df.to_csv("universe.csv", index=False)
    except Exception:
        pass
    df = pd.read_csv("universe.csv").rename(columns={"Company Name": "name", "Symbol": "symbol"})
    return df[["symbol", "name"]].dropna().reset_index(drop=True)
