"""Fetch OHLCV data from TwelveData API."""
import logging
import requests
import pandas as pd
from datetime import datetime, timezone

log = logging.getLogger(__name__)

TWELVEDATA_BASE = "https://api.twelvedata.com/time_series"


def _fetch(api_key: str, symbol: str, interval: str, outputsize: int) -> pd.DataFrame:
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "format": "JSON",
        "apikey": api_key,
        "timezone": "UTC",
    }
    resp = requests.get(TWELVEDATA_BASE, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") == "error":
        raise ValueError(f"TwelveData error: {data.get('message')}")

    values = data["values"]
    df = pd.DataFrame(values)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col])
    df = df.sort_values("datetime").reset_index(drop=True)
    return df[["datetime", "open", "high", "low", "close"]]


def fetch_1h(api_key: str, outputsize: int = 20) -> pd.DataFrame:
    return _fetch(api_key, "XAU/USD", "1h", outputsize)


def fetch_5m(api_key: str, outputsize: int = 50) -> pd.DataFrame:
    return _fetch(api_key, "XAU/USD", "5min", outputsize)


if __name__ == "__main__":
    import os, sys
    logging.basicConfig(level=logging.INFO)
    key = os.environ.get("TWELVEDATA_API_KEY", "")
    if not key:
        print("Set TWELVEDATA_API_KEY to test live fetch")
        sys.exit(0)
    df1h = fetch_1h(key)
    df5m = fetch_5m(key)
    print("1H tail:")
    print(df1h.tail(3).to_string())
    print("\n5m tail:")
    print(df5m.tail(3).to_string())
