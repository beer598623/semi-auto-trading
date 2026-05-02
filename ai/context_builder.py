"""Build the structured context string passed to Claude."""
import pandas as pd
from datetime import timezone
from strategy.signal_filter import SignalResult


def build_context(
    signal: SignalResult,
    df_1h: pd.DataFrame,
    df_5m: pd.DataFrame,
    calendar_events: list[dict],
    recent_trades: list[dict],
) -> str:
    i1 = signal.indicators_1h
    i5 = signal.indicators_5m

    lines = []

    # ── Indicator snapshot
    lines.append("=== INDICATOR SNAPSHOT ===")
    lines.append("Timeframe: 1H")
    lines.append(f"  EMA21: {i1['ema21']} | EMA50: {i1['ema50']} | Trend: {i1['trend']}")
    lines.append(f"  ADX: {i1['adx']} | ATR: {i1['atr']}")
    lines.append("")
    lines.append("Timeframe: 5m")
    lines.append(f"  BB Upper: {i5['bb_upper']} | BB Mid: {i5['bb_mid']} | BB Lower: {i5['bb_lower']}")
    lines.append(f"  RSI: {i5['rsi']} | Prev RSI: {i5['rsi_prev']} | RSI Direction: {'TURNING UP' if signal.direction == 'BUY' else 'TURNING DOWN'}")
    lines.append(f"  ATR: {i5['atr']} | ATR Avg(20): {i5['atr_avg_20']}")
    lines.append("")

    # ── Signal details
    lines.append("=== SIGNAL ===")
    lines.append(f"Direction: {signal.direction}")
    lines.append(
        f"Entry: {signal.entry} | SL: {signal.sl} | TP: {signal.tp} | SL Dist: {signal.sl_dist} pts"
    )
    lines.append(f"BE Level: {signal.be_level} | Lot: {signal.lot}")
    lines.append(f"Session: {signal.session} | Regime: {signal.regime}")
    lines.append("")

    # ── 1H price action
    lines.append("=== 1H PRICE ACTION (Last 20 bars) ===")
    for _, row in df_1h.tail(20).iterrows():
        dt  = row["datetime"].strftime("%Y-%m-%d %H:%M")
        rng = round(row["high"] - row["low"], 3)
        direction = "UP" if row["close"] >= row["open"] else "DOWN"
        lines.append(
            f"[{dt}] O:{row['open']:.2f} H:{row['high']:.2f} L:{row['low']:.2f} C:{row['close']:.2f}"
            f" | Range:{rng} | Dir:{direction}"
        )
    lines.append("")

    # ── 5m price action
    lines.append("=== 5m PRICE ACTION (Last 50 bars) ===")
    for _, row in df_5m.tail(50).iterrows():
        dt  = row["datetime"].strftime("%Y-%m-%d %H:%M")
        rng = round(row["high"] - row["low"], 3)
        direction = "UP" if row["close"] >= row["open"] else "DOWN"
        lines.append(
            f"[{dt}] O:{row['open']:.2f} H:{row['high']:.2f} L:{row['low']:.2f} C:{row['close']:.2f}"
            f" | Range:{rng} | Dir:{direction}"
        )
    lines.append("")

    # ── Economic calendar
    lines.append("=== ECONOMIC CALENDAR (±2 hours) ===")
    if calendar_events:
        for ev in calendar_events:
            lines.append(
                f"[{ev['time_utc']}] | {ev['currency']} | {ev['event']} | "
                f"Impact: {ev['impact']} | Forecast: {ev.get('forecast', '')} | "
                f"Previous: {ev.get('previous', '')}"
            )
    else:
        lines.append("No high-impact events in the next 2 hours.")
    lines.append("")

    # ── Recent trades
    lines.append("=== RECENT TRADES (Last 5) ===")
    if recent_trades:
        for t in recent_trades[-5:]:
            dt     = t.get("timestamp", "N/A")
            direc  = t.get("direction", "")
            entry  = t.get("entry", "")
            exit_p = t.get("exit_price", "")
            result = t.get("result", "")
            pnl    = t.get("pnl", "")
            regime = t.get("regime", "")
            sess   = t.get("session", "")
            lines.append(
                f"[{dt}] {direc} @ {entry} → {exit_p} | {result} ${pnl} | {regime} | {sess}"
            )
    else:
        lines.append("No recent trades available.")

    return "\n".join(lines)


if __name__ == "__main__":
    import os, sys, numpy as np
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from strategy.signal_filter import SignalResult
    import pandas as pd

    sig = SignalResult(
        direction="BUY", entry=1913.0, sl=1909.5, tp=1921.75,
        sl_dist=3.5, lot=0.01, be_level=1914.5,
        session="London", regime="trend",
        indicators_1h={"ema21": 1912.0, "ema50": 1905.0, "adx": 27.3, "atr": 2.1,
                        "trend": "BULLISH", "ema_spread_pct": 0.37},
        indicators_5m={"bb_upper": 1916.0, "bb_mid": 1912.0, "bb_lower": 1908.0,
                        "rsi": 44.2, "rsi_prev": 41.0, "atr": 1.8, "atr_avg_20": 1.4,
                        "regime": "trend"},
    )

    np.random.seed(0)
    df1h = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=20, freq="1h", tz="UTC"),
        "open": np.random.uniform(1900, 1920, 20),
        "high": np.random.uniform(1920, 1930, 20),
        "low":  np.random.uniform(1890, 1900, 20),
        "close":np.random.uniform(1900, 1920, 20),
    })
    df5m = pd.DataFrame({
        "datetime": pd.date_range("2024-01-02", periods=50, freq="5min", tz="UTC"),
        "open": np.random.uniform(1900, 1920, 50),
        "high": np.random.uniform(1920, 1925, 50),
        "low":  np.random.uniform(1895, 1900, 50),
        "close":np.random.uniform(1900, 1920, 50),
    })

    ctx = build_context(sig, df1h, df5m, [], [])
    print(ctx)
