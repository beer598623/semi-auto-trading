"""Rule-based signal filter for XAUUSD MTF BB Pullback v2.5."""
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from config import settings as cfg

log = logging.getLogger(__name__)


# ── Indicator calculations ──────────────────────────────────────────────────

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_g = gain.ewm(com=period - 1, adjust=False).mean()
    avg_l = loss.ewm(com=period - 1, adjust=False).mean()
    rs    = avg_g / avg_l.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hi, lo, cl = df["high"], df["low"], df["close"]
    prev_cl = cl.shift(1)
    tr = pd.concat([
        hi - lo,
        (hi - prev_cl).abs(),
        (lo - prev_cl).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, adjust=False).mean()


def bollinger(series: pd.Series, period: int = 20, stddev: float = 2.0):
    mid   = series.rolling(period).mean()
    std   = series.rolling(period).std()
    upper = mid + stddev * std
    lower = mid - stddev * std
    return upper, mid, lower


def adx(df: pd.DataFrame, period: int = 10) -> pd.Series:
    hi, lo, cl = df["high"], df["low"], df["close"]
    prev_hi = hi.shift(1)
    prev_lo = lo.shift(1)
    prev_cl = cl.shift(1)

    tr = pd.concat([
        hi - lo,
        (hi - prev_cl).abs(),
        (lo - prev_cl).abs(),
    ], axis=1).max(axis=1)

    dm_plus  = (hi - prev_hi).clip(lower=0)
    dm_minus = (prev_lo - lo).clip(lower=0)
    # zero out where the other is larger
    mask = dm_plus >= dm_minus
    dm_plus  = dm_plus.where(mask, 0.0)
    dm_minus = dm_minus.where(~mask, 0.0)

    atr_s    = tr.ewm(com=period - 1, adjust=False).mean()
    di_plus  = 100 * dm_plus.ewm(com=period - 1, adjust=False).mean() / atr_s.replace(0, np.nan)
    di_minus = 100 * dm_minus.ewm(com=period - 1, adjust=False).mean() / atr_s.replace(0, np.nan)

    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus).replace(0, np.nan)
    return dx.ewm(com=period - 1, adjust=False).mean()


# ── Data structures ─────────────────────────────────────────────────────────

@dataclass
class SignalResult:
    direction: str           # "BUY" | "SELL"
    entry: float
    sl: float
    tp: float
    sl_dist: float
    lot: float
    be_level: float
    session: str
    regime: str
    indicators_1h: dict
    indicators_5m: dict
    skip_reason: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.skip_reason is None


@dataclass
class NoSignal:
    reason: str
    indicators_1h: dict = field(default_factory=dict)
    indicators_5m: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return False


# ── Time guards ──────────────────────────────────────────────────────────────

def _current_session(now: datetime) -> str:
    h = now.hour
    if 6 <= h < 12:
        return "London"
    if 12 <= h < 18:
        return "NY"
    if 18 <= h < 22:
        return "NY_Late"
    return "Asia"


def _is_skip_time(now: datetime) -> Optional[str]:
    wd = now.weekday()   # 0=Mon … 6=Sun
    if wd == 5:
        return "Weekend Saturday"
    if wd == 6:
        return "Weekend Sunday"
    if wd == 4 and now.hour >= 23:
        return "Friday 23:00+ UTC"

    h, m = now.hour, now.minute
    rs, re = cfg.ROLLOVER_START, cfg.ROLLOVER_END
    if (h, m) >= rs and (h, m) <= re:
        return f"Rollover window {rs[0]:02d}:{rs[1]:02d}-{re[0]:02d}:{re[1]:02d}"

    if not (cfg.SESSION_START_UTC <= h < cfg.SESSION_END_UTC):
        return f"Outside session window {cfg.SESSION_START_UTC:02d}:00-{cfg.SESSION_END_UTC:02d}:00 UTC"

    return None


# ── Lot sizing ───────────────────────────────────────────────────────────────

def _calc_lot(balance: float, risk_pct: float, sl_dist: float) -> float:
    risk_amount = balance * (risk_pct / 100)
    # sl_dist is in price points; 1 lot = 100 oz, pip value = $1/0.01pt for XAU
    # Exness MT5 XAUUSD: 1 lot = 100 oz, value per pt = $100/pt
    # lot = risk_amount / (sl_dist * 100)
    raw = risk_amount / (sl_dist * 100)
    lot = math.floor(raw / 0.01) * 0.01
    return max(lot, 0.01)


# ── Main filter ──────────────────────────────────────────────────────────────

def run_filter(
    df_1h: pd.DataFrame,
    df_5m: pd.DataFrame,
    balance: float,
    risk_pct: float,
    recent_trades: list[dict] | None = None,
) -> SignalResult | NoSignal:
    now = datetime.now(timezone.utc)

    # ── Time guards
    skip = _is_skip_time(now)
    if skip:
        return NoSignal(reason=skip)

    session = _current_session(now)

    # ── Loss streak check (today UTC only — resets each new trading day)
    if recent_trades:
        today_prefix = now.date().isoformat()   # e.g. "2026-05-05"
        todays = [
            t for t in recent_trades
            if str(t.get("timestamp", "")).startswith(today_prefix)
        ]
        last = todays[-cfg.MAX_LOSS_STREAK:]
        if len(last) == cfg.MAX_LOSS_STREAK and all(t.get("result") == "LOSS" for t in last):
            return NoSignal(reason=f"Loss streak >= {cfg.MAX_LOSS_STREAK} today (auto-resets tomorrow)")

    # ── 1H indicators
    ema21  = ema(df_1h["close"], cfg.EMA_FAST)
    ema50  = ema(df_1h["close"], cfg.EMA_SLOW)
    adx_s  = adx(df_1h, cfg.ADX_PERIOD)
    atr_1h = atr(df_1h, cfg.ATR_PERIOD)

    e21 = float(ema21.iloc[-1])
    e50 = float(ema50.iloc[-1])
    adx_val  = float(adx_s.iloc[-1])
    atr_1h_val = float(atr_1h.iloc[-1])
    ema_spread = abs(e21 - e50) / e50

    indicators_1h = {
        "ema21": round(e21, 3),
        "ema50": round(e50, 3),
        "adx":   round(adx_val, 2),
        "atr":   round(atr_1h_val, 3),
        "trend": "BULLISH" if e21 > e50 else "BEARISH",
        "ema_spread_pct": round(ema_spread * 100, 4),
    }

    # ADX filter
    if adx_val < cfg.ADX_MIN:
        return NoSignal(reason=f"ADX {adx_val:.1f} < {cfg.ADX_MIN}", indicators_1h=indicators_1h)

    # EMA spread filter
    if ema_spread < cfg.EMA_SPREAD_MIN:
        return NoSignal(reason=f"EMA spread {ema_spread*100:.3f}% < 0.1% (flat)", indicators_1h=indicators_1h)

    bullish_1h = e21 > e50

    # ── 5m indicators
    bb_up, bb_mid, bb_lo = bollinger(df_5m["close"], cfg.BB_PERIOD, cfg.BB_STDDEV)
    rsi_s  = rsi(df_5m["close"], cfg.RSI_PERIOD)
    atr_5m = atr(df_5m, cfg.ATR_PERIOD)

    cur_close  = float(df_5m["close"].iloc[-1])
    prev_close = float(df_5m["close"].iloc[-2])
    prev_low   = float(df_5m["low"].iloc[-2])
    prev_high  = float(df_5m["high"].iloc[-2])

    bb_upper_val = float(bb_up.iloc[-1])
    bb_mid_val   = float(bb_mid.iloc[-1])
    bb_lower_val = float(bb_lo.iloc[-1])

    rsi_cur  = float(rsi_s.iloc[-1])
    rsi_prev = float(rsi_s.iloc[-2])

    atr_cur     = float(atr_5m.iloc[-1])
    atr_avg_20  = float(atr_5m.iloc[-20:].mean())

    regime = "trend" if adx_val >= 25 else "range"

    indicators_5m = {
        "bb_upper":   round(bb_upper_val, 3),
        "bb_mid":     round(bb_mid_val, 3),
        "bb_lower":   round(bb_lower_val, 3),
        "rsi":        round(rsi_cur, 2),
        "rsi_prev":   round(rsi_prev, 2),
        "atr":        round(atr_cur, 3),
        "atr_avg_20": round(atr_avg_20, 3),
        "regime":     regime,
    }

    # ATR activity filter
    if atr_cur < atr_avg_20 * cfg.ATR_MULT_MIN:
        return NoSignal(
            reason=f"ATR {atr_cur:.3f} < avg*1.2 ({atr_avg_20*1.2:.3f}) — low volatility",
            indicators_1h=indicators_1h, indicators_5m=indicators_5m,
        )

    # ── BUY conditions
    if bullish_1h:
        buy_bb_breach  = prev_low < bb_lower_val
        buy_bb_close   = cur_close > bb_lower_val
        buy_rsi        = rsi_prev < cfg.RSI_BUY_MAX and rsi_cur > rsi_prev

        if not buy_bb_breach:
            return NoSignal(reason="BUY: prev_low did not breach BB lower", indicators_1h=indicators_1h, indicators_5m=indicators_5m)
        if not buy_bb_close:
            return NoSignal(reason="BUY: close not back above BB lower", indicators_1h=indicators_1h, indicators_5m=indicators_5m)
        if not buy_rsi:
            return NoSignal(reason=f"BUY: RSI not turning up (prev={rsi_prev:.1f}, cur={rsi_cur:.1f})", indicators_1h=indicators_1h, indicators_5m=indicators_5m)

        entry   = cur_close
        sl      = round(prev_low - cfg.SL_ATR_BUFFER * atr_cur, 3)
        sl_dist = round(entry - sl, 3)

        if sl_dist > cfg.SL_ATR_MULT_MAX * atr_cur:
            return NoSignal(reason=f"BUY: SL dist {sl_dist:.3f} > 3*ATR {3*atr_cur:.3f}", indicators_1h=indicators_1h, indicators_5m=indicators_5m)

        tp       = round(entry + cfg.TP_R_MULT * sl_dist, 3)
        be_level = round(entry + cfg.BE_ATR_MULT * atr_cur, 3)
        lot      = _calc_lot(balance, risk_pct, sl_dist)

        return SignalResult(
            direction="BUY", entry=entry, sl=sl, tp=tp,
            sl_dist=sl_dist, lot=lot, be_level=be_level,
            session=session, regime=regime,
            indicators_1h=indicators_1h, indicators_5m=indicators_5m,
        )

    # ── SELL conditions
    else:
        sell_bb_breach = prev_high > bb_upper_val
        sell_bb_close  = cur_close < bb_upper_val
        sell_rsi       = rsi_prev > cfg.RSI_SELL_MIN and rsi_cur < rsi_prev

        if not sell_bb_breach:
            return NoSignal(reason="SELL: prev_high did not breach BB upper", indicators_1h=indicators_1h, indicators_5m=indicators_5m)
        if not sell_bb_close:
            return NoSignal(reason="SELL: close not back below BB upper", indicators_1h=indicators_1h, indicators_5m=indicators_5m)
        if not sell_rsi:
            return NoSignal(reason=f"SELL: RSI not turning down (prev={rsi_prev:.1f}, cur={rsi_cur:.1f})", indicators_1h=indicators_1h, indicators_5m=indicators_5m)

        entry   = cur_close
        sl      = round(prev_high + cfg.SL_ATR_BUFFER * atr_cur, 3)
        sl_dist = round(sl - entry, 3)

        if sl_dist > cfg.SL_ATR_MULT_MAX * atr_cur:
            return NoSignal(reason=f"SELL: SL dist {sl_dist:.3f} > 3*ATR {3*atr_cur:.3f}", indicators_1h=indicators_1h, indicators_5m=indicators_5m)

        tp       = round(entry - cfg.TP_R_MULT * sl_dist, 3)
        be_level = round(entry - cfg.BE_ATR_MULT * atr_cur, 3)
        lot      = _calc_lot(balance, risk_pct, sl_dist)

        return SignalResult(
            direction="SELL", entry=entry, sl=sl, tp=tp,
            sl_dist=sl_dist, lot=lot, be_level=be_level,
            session=session, regime=regime,
            indicators_1h=indicators_1h, indicators_5m=indicators_5m,
        )


if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    logging.basicConfig(level=logging.INFO)

    # Build synthetic 1H data (bullish trend)
    np.random.seed(42)
    base = 1900.0
    closes_1h = base + np.cumsum(np.random.randn(60) * 0.5)
    closes_1h += np.linspace(0, 15, 60)   # uptrend
    df1h = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=60, freq="1h", tz="UTC"),
        "open":  closes_1h - np.abs(np.random.randn(60) * 0.3),
        "high":  closes_1h + np.abs(np.random.randn(60) * 0.8),
        "low":   closes_1h - np.abs(np.random.randn(60) * 0.8),
        "close": closes_1h,
    })

    # Build synthetic 5m data that triggers a BUY
    closes_5m = np.ones(55) * 1912.0
    closes_5m[-2] = 1910.5   # prev_low will be below BB lower
    closes_5m[-1] = 1913.0   # close back above
    df5m = pd.DataFrame({
        "datetime": pd.date_range("2024-01-03 07:00", periods=55, freq="5min", tz="UTC"),
        "open":  closes_5m - 0.2,
        "high":  closes_5m + 0.5,
        "low":   closes_5m - 0.8,
        "close": closes_5m,
    })
    # Force prev candle low below BB lower (~1911 area)
    df5m.loc[df5m.index[-2], "low"] = 1909.0

    result = run_filter(df1h, df5m, balance=100.0, risk_pct=1.0)
    print(type(result).__name__, result)
