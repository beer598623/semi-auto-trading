"""Log trade signals to Notion database."""
import logging
from datetime import datetime, timezone
from typing import Optional

import requests

from strategy.signal_filter import SignalResult

log = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def _prop_title(text: str) -> dict:
    return {"title": [{"text": {"content": text}}]}


def _prop_date(dt: datetime) -> dict:
    return {"date": {"start": dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")}}


def _prop_number(val: Optional[float]) -> dict:
    return {"number": val}


def _prop_select(val: str) -> dict:
    return {"select": {"name": val}}


def _prop_text(val: str) -> dict:
    return {"rich_text": [{"text": {"content": str(val)[:2000]}}]}


def log_signal(
    signal: SignalResult,
    verdict: dict,
    notion_token: str,
    database_id: str,
) -> bool:
    """Create a page in Notion database for this signal. Returns True on success."""
    now = datetime.now(timezone.utc)
    ts  = now.strftime("%Y-%m-%d %H:%M UTC")

    risk_flags_text = ", ".join(str(f) for f in verdict.get("risk_flags", [])) or "none"
    reasoning_text  = str(verdict.get("reasoning", ""))

    title_text = f"{signal.direction} @ {signal.entry} | {ts}"

    properties = {
        "Signal":            _prop_title(title_text),
        "Timestamp":         _prop_date(now),
        "Direction":         _prop_select(signal.direction),
        "Entry":             _prop_number(signal.entry),
        "SL":                _prop_number(signal.sl),
        "TP":                _prop_number(signal.tp),
        "SL Dist":           _prop_number(signal.sl_dist),
        "Lot":               _prop_number(signal.lot),
        "Session":           _prop_select(signal.session),
        "Regime":            _prop_select(signal.regime),
        "ADX":               _prop_number(signal.indicators_1h.get("adx")),
        "RSI":               _prop_number(signal.indicators_5m.get("rsi")),
        "ATR":               _prop_number(signal.indicators_5m.get("atr")),
        "Claude Verdict":    _prop_select(verdict.get("verdict", "NO-GO")),
        "Claude Confidence": _prop_select(verdict.get("confidence", "LOW")),
        "Claude Reasoning":  _prop_text(reasoning_text),
        "Claude Risk Flags": _prop_text(risk_flags_text),
        "Claude Adjustment": _prop_select(verdict.get("suggested_adjustment", "none")),
        "News Risk":         _prop_select(verdict.get("news_risk", "none")),
        "Action":            _prop_select("CONFIRM"),
    }

    payload = {
        "parent": {"database_id": database_id},
        "properties": properties,
    }

    try:
        resp = requests.post(
            NOTION_API,
            headers=_headers(notion_token),
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        page_id = resp.json().get("id", "unknown")
        log.info("Notion page created: %s", page_id)
        return True

    except requests.HTTPError as exc:
        log.error("Notion HTTP error %s: %s", exc.response.status_code, exc.response.text[:300])
        return False
    except requests.RequestException as exc:
        log.error("Notion request failed: %s", exc)
        return False


def fetch_recent_trades(
    notion_token: str,
    database_id: str,
    limit: int = 5,
) -> list[dict]:
    """Fetch last N completed trades from Notion (those with Exit Price set)."""
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    payload = {
        "filter": {
            "property": "Exit Price",
            "number": {"is_not_empty": True},
        },
        "sorts": [{"property": "Timestamp", "direction": "descending"}],
        "page_size": limit,
    }

    try:
        resp = requests.post(
            url,
            headers=_headers(notion_token),
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        trades = []
        for page in results:
            props = page.get("properties", {})

            def get_num(key):
                n = props.get(key, {}).get("number")
                return n

            def get_sel(key):
                s = props.get(key, {}).get("select")
                return s["name"] if s else ""

            def get_date(key):
                d = props.get(key, {}).get("date")
                return d["start"] if d else ""

            entry_val = get_num("Entry")
            exit_val  = get_num("Exit Price")
            pnl_val   = get_num("PnL")
            action    = get_sel("Action")

            result_str = "WIN" if (pnl_val or 0) > 0 else "LOSS"

            trades.append({
                "timestamp": get_date("Timestamp"),
                "direction": get_sel("Direction"),
                "entry":     entry_val,
                "exit_price": exit_val,
                "pnl":       pnl_val,
                "result":    result_str,
                "regime":    get_sel("Regime"),
                "session":   get_sel("Session"),
                "action":    action,
            })
        return trades

    except Exception as exc:
        log.warning("Could not fetch recent trades from Notion: %s", exc)
        return []


if __name__ == "__main__":
    import os, sys, json
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    logging.basicConfig(level=logging.INFO)

    from strategy.signal_filter import SignalResult

    sig = SignalResult(
        direction="BUY", entry=1913.0, sl=1909.5, tp=1921.75,
        sl_dist=3.5, lot=0.01, be_level=1914.8,
        session="London", regime="trend",
        indicators_1h={"ema21": 1912.0, "ema50": 1905.0, "adx": 27.3, "atr": 2.1,
                        "trend": "BULLISH", "ema_spread_pct": 0.37},
        indicators_5m={"bb_upper": 1916.0, "bb_mid": 1912.0, "bb_lower": 1908.0,
                        "rsi": 44.2, "rsi_prev": 41.0, "atr": 1.8, "atr_avg_20": 1.4,
                        "regime": "trend"},
    )

    verdict = {
        "verdict": "GO", "confidence": "HIGH",
        "reasoning": "Test entry",
        "key_levels": [1908, 1920],
        "risk_flags": [],
        "suggested_adjustment": "none",
        "news_risk": "none",
        "trade_pattern_note": "none",
    }

    token = os.environ.get("NOTION_TOKEN", "")
    db_id = os.environ.get("NOTION_DATABASE_ID", "")
    if not token or not db_id:
        print("Set NOTION_TOKEN and NOTION_DATABASE_ID to test")
    else:
        ok = log_signal(sig, verdict, token, db_id)
        print("Logged:", ok)
        trades = fetch_recent_trades(token, db_id)
        print("Recent trades:", json.dumps(trades, indent=2, default=str))
