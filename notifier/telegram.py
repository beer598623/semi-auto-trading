"""Send trading signal alerts via Telegram Bot API."""
import logging

import requests

from strategy.signal_filter import SignalResult

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _format_message(signal: SignalResult, verdict: dict) -> str:
    direction_icon = "🟢" if signal.direction == "BUY" else "🔴"
    sep = "─" * 29

    verdict_str    = verdict.get("verdict", "N/A")
    confidence_str = verdict.get("confidence", "N/A")
    reasoning      = verdict.get("reasoning", "")
    key_levels     = verdict.get("key_levels", [])
    risk_flags     = verdict.get("risk_flags", [])
    news_risk      = verdict.get("news_risk", "none")
    adjustment     = verdict.get("suggested_adjustment", "none")

    key_levels_str = str(key_levels) if key_levels else "None"
    risk_flags_str = ", ".join(str(f) for f in risk_flags) if risk_flags else "None"

    sl_pts = round(abs(signal.entry - signal.sl), 2)
    tp_pts = round(abs(signal.tp - signal.entry), 2)
    sl_sign = "-" if signal.direction == "BUY" else "+"
    tp_sign = "+" if signal.direction == "BUY" else "-"

    lines = [
        f"{direction_icon} {signal.direction} SIGNAL — XAUUSD",
        sep,
        f"Entry : {signal.entry}",
        f"SL    : {signal.sl}  ({sl_sign}{sl_pts} pts)",
        f"TP    : {signal.tp}  ({tp_sign}{tp_pts} pts)",
        f"Lot   : {signal.lot}",
        sep,
        f"Session : {signal.session}  |  Regime : {signal.regime.capitalize()}",
        f"ADX     : {signal.indicators_1h['adx']}  |  RSI : {signal.indicators_5m['rsi']}",
        sep,
        "📊 Claude Analysis",
        f"Verdict    : {verdict_str} — {confidence_str} confidence",
        f"Reasoning  : {reasoning}",
        f"Key levels : {key_levels_str}",
        f"Risk flags : {risk_flags_str}",
        f"News risk  : {news_risk.capitalize() if news_risk != 'none' else 'None'}",
        f"Adjustment : {adjustment.replace('_', ' ').capitalize() if adjustment != 'none' else 'None'}",
        sep,
    ]

    if news_risk and news_risk != "none":
        lines.append(f"⚠️ NEWS RISK: {news_risk.upper()}")

    return "\n".join(lines)


def send_signal(
    signal: SignalResult,
    verdict: dict,
    bot_token: str,
    chat_id: str,
) -> bool:
    """Send formatted signal to Telegram. Returns True on success."""
    text = _format_message(signal, verdict)
    url  = TELEGRAM_API.format(token=bot_token)

    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            log.error("Telegram API returned not-ok: %s", data)
            return False
        log.info("Telegram signal sent OK (message_id=%s)", data["result"]["message_id"])
        return True

    except requests.RequestException as exc:
        log.error("Telegram send failed: %s", exc)
        return False


def send_text(message: str, bot_token: str, chat_id: str) -> bool:
    """Send a plain text message."""
    url = TELEGRAM_API.format(token=bot_token)
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": message},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("ok", False)
    except requests.RequestException as exc:
        log.error("Telegram text send failed: %s", exc)
        return False


if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from strategy.signal_filter import SignalResult

    sig = SignalResult(
        direction="SELL", entry=4693.50, sl=4701.20, tp=4674.55,
        sl_dist=7.70, lot=0.01, be_level=4685.8,
        session="NY", regime="trend",
        indicators_1h={"ema21": 4690.0, "ema50": 4700.0, "adx": 26.9, "atr": 5.1,
                        "trend": "BEARISH", "ema_spread_pct": 0.23},
        indicators_5m={"bb_upper": 4700.0, "bb_mid": 4693.0, "bb_lower": 4686.0,
                        "rsi": 57.3, "rsi_prev": 61.0, "atr": 4.8, "atr_avg_20": 3.9,
                        "regime": "trend"},
    )

    verdict = {
        "verdict": "GO", "confidence": "HIGH",
        "reasoning": "Clean rejection from BB upper with RSI divergence. Structure supports continuation.",
        "key_levels": [4700, 4710],
        "risk_flags": [],
        "suggested_adjustment": "none",
        "news_risk": "none",
        "trade_pattern_note": "none",
    }

    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        msg = _format_message(sig, verdict)
        print("=== FORMATTED MESSAGE ===")
        print(msg)
    else:
        ok = send_signal(sig, verdict, token, chat_id)
        print("Sent:", ok)
