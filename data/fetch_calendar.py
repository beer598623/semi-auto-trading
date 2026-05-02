"""Fetch high-impact USD events from ForexFactory RSS within ±2 hours of now."""
import logging
import warnings
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests
from dateutil import parser as dtparser

log = logging.getLogger(__name__)

FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
FF_RSS = "https://forexfactory.com/ffcal_week_this.xml"

# ForexFactory times are US Eastern — map to UTC offset (handle DST naively via fixed offsets)
# We'll parse via dateutil with a fallback

WINDOW_HOURS = 2


def _to_utc(dt_str: str) -> datetime | None:
    """Parse a ForexFactory datetime string to UTC. Returns None on failure."""
    try:
        # ForexFactory format example: "01-01-2024 8:30am"
        # dateutil handles this; assume Eastern time = UTC-5 (EST) / UTC-4 (EDT)
        import pytz
        eastern = pytz.timezone("America/New_York")
        dt_naive = dtparser.parse(dt_str, dayfirst=False)
        dt_eastern = eastern.localize(dt_naive)
        return dt_eastern.astimezone(timezone.utc)
    except Exception:
        return None


def fetch_calendar(window_hours: int = WINDOW_HOURS) -> list[dict]:
    """Return list of high-impact USD events within ±window_hours of now (UTC)."""
    now = datetime.now(timezone.utc)
    lo = now - timedelta(hours=window_hours)
    hi = now + timedelta(hours=window_hours)

    events = []
    try:
        resp = requests.get(FF_RSS, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        for item in root.iter("event"):
            currency = (item.findtext("country") or "").strip().upper()
            impact   = (item.findtext("impact") or "").strip().lower()
            if currency != "USD" or impact != "high":
                continue

            title    = item.findtext("title") or ""
            date_str = item.findtext("date") or ""
            time_str = item.findtext("time") or ""
            forecast = item.findtext("forecast") or ""
            previous = item.findtext("previous") or ""

            dt_str = f"{date_str} {time_str}".strip()
            event_utc = _to_utc(dt_str) if dt_str else None

            if event_utc and lo <= event_utc <= hi:
                events.append({
                    "time_utc": event_utc.strftime("%H:%M UTC"),
                    "currency": "USD",
                    "event": title,
                    "impact": "HIGH",
                    "forecast": forecast,
                    "previous": previous,
                })

    except requests.RequestException as exc:
        log.warning("Calendar fetch failed (network): %s", exc)
    except ET.ParseError as exc:
        log.warning("Calendar XML parse error: %s", exc)
    except Exception as exc:
        log.warning("Calendar unexpected error: %s", exc)

    return events


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    evts = fetch_calendar()
    if evts:
        for e in evts:
            print(e)
    else:
        print("No high-impact USD events in window (or fetch failed).")
