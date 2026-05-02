"""XAUUSD MTF BB Pullback v2.5 — Semi-auto signal generator."""
import logging
import sys
import time
from datetime import datetime, timezone

from config import settings as cfg
from data.fetch_ohlcv import fetch_1h, fetch_5m
from data.fetch_calendar import fetch_calendar
from strategy.signal_filter import run_filter, SignalResult
from ai.context_builder import build_context
from ai.analyst import get_verdict
from notifier.telegram import send_signal, send_text
from logger.notion import log_signal, fetch_recent_trades

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("main")


def _loop_iteration(iteration: int) -> None:
    now = datetime.now(timezone.utc)
    log.info("=== Iteration %d | %s UTC ===", iteration, now.strftime("%Y-%m-%d %H:%M"))

    # ── Fetch data
    log.info("Fetching OHLCV data...")
    df_1h = fetch_1h(cfg.TWELVEDATA_API_KEY, outputsize=55)
    df_5m = fetch_5m(cfg.TWELVEDATA_API_KEY, outputsize=55)
    log.info("1H bars: %d | 5m bars: %d", len(df_1h), len(df_5m))

    # ── Fetch recent trades for loss-streak check
    recent_trades = fetch_recent_trades(cfg.NOTION_TOKEN, cfg.NOTION_DATABASE_ID, limit=5)

    # ── Run signal filter
    result = run_filter(df_1h, df_5m, cfg.ACCOUNT_BALANCE, cfg.RISK_PERCENT, recent_trades)

    i1 = getattr(result, "indicators_1h", {})
    i5 = getattr(result, "indicators_5m", {})

    log.info(
        "1H: EMA21=%.2f EMA50=%.2f ADX=%.1f | 5m: RSI=%.1f ATR=%.3f",
        i1.get("ema21", 0), i1.get("ema50", 0), i1.get("adx", 0),
        i5.get("rsi", 0),   i5.get("atr", 0),
    )

    if not result.passed:
        log.info("NO_SIGNAL: %s", result.reason)
        return

    signal: SignalResult = result
    log.info(
        "SIGNAL: %s | Entry=%.3f SL=%.3f TP=%.3f Lot=%.2f",
        signal.direction, signal.entry, signal.sl, signal.tp, signal.lot,
    )

    # ── Calendar
    calendar_events = fetch_calendar()
    if calendar_events:
        log.info("Calendar events in window: %d", len(calendar_events))

    # ── Build context and call Claude
    context = build_context(signal, df_1h, df_5m, calendar_events, recent_trades)
    log.info("Calling Claude for verdict...")
    verdict = get_verdict(context, cfg.ANTHROPIC_API_KEY)
    log.info(
        "Claude verdict: %s | confidence: %s | news_risk: %s",
        verdict.get("verdict"), verdict.get("confidence"), verdict.get("news_risk"),
    )

    # ── Send Telegram notification
    ok_tg = send_signal(signal, verdict, cfg.TELEGRAM_BOT_TOKEN, cfg.TELEGRAM_CHAT_ID)
    if ok_tg:
        log.info("Telegram signal sent.")
    else:
        log.warning("Telegram send failed.")

    # ── Log to Notion
    ok_notion = log_signal(signal, verdict, cfg.NOTION_TOKEN, cfg.NOTION_DATABASE_ID)
    if ok_notion:
        log.info("Notion page created.")
    else:
        log.warning("Notion log failed.")


def main() -> None:
    start_time = time.monotonic()
    runtime_sec = cfg.RUNTIME_MINUTES * 60
    iteration   = 0

    log.info("XAUUSD Signal Generator starting | runtime=%dm loop=%ds",
             cfg.RUNTIME_MINUTES, cfg.LOOP_INTERVAL_SEC)

    while True:
        elapsed = time.monotonic() - start_time
        if elapsed >= runtime_sec:
            log.info("Runtime limit reached (%.0f min). Shutting down.", elapsed / 60)
            break

        iteration += 1
        try:
            _loop_iteration(iteration)
        except Exception as exc:
            log.exception("Unhandled error in iteration %d: %s", iteration, exc)
            try:
                send_text(
                    f"⚠️ Signal bot error (iter {iteration}): {exc}",
                    cfg.TELEGRAM_BOT_TOKEN, cfg.TELEGRAM_CHAT_ID,
                )
            except Exception:
                pass

        # Sleep until next iteration, respecting runtime limit
        elapsed = time.monotonic() - start_time
        remaining = runtime_sec - elapsed
        sleep_time = min(cfg.LOOP_INTERVAL_SEC, remaining)
        if sleep_time > 0:
            log.info("Sleeping %.0fs until next iteration...", sleep_time)
            time.sleep(sleep_time)


if __name__ == "__main__":
    main()
