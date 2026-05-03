"""Call Claude API and parse structured trading verdict."""
import json
import logging

import anthropic

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Senior Quantitative Strategist specializing in XAUUSD (Gold vs US Dollar).
You have deep expertise in price action analysis, market microstructure, and systematic trading.

A rule-based filter has identified a candidate signal. Your job is to:
1. Analyze the price action context leading up to this signal
2. Assess whether the setup is clean or borderline based on structure
3. Check if any economic events create risk
4. Review recent trade history for patterns
5. Produce a structured verdict

You must respond ONLY in valid JSON — no preamble, no explanation outside the JSON."""

RESPONSE_SCHEMA = {
    "verdict": "GO | NO-GO | CAUTION",
    "confidence": "HIGH | MEDIUM | LOW",
    "reasoning": "2-3 sentences on price action context",
    "key_levels": ["level1", "level2"],
    "risk_flags": ["flag1", "flag2"],
    "suggested_adjustment": "none | reduce_lot | widen_sl | tighten_sl",
    "news_risk": "none | low | high",
    "trade_pattern_note": "observation from recent trades or none",
}

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1000

FALLBACK = {
    "verdict": "NO-GO",
    "confidence": "LOW",
    "reasoning": "Claude response was invalid or unavailable.",
    "key_levels": [],
    "risk_flags": ["parse_error"],
    "suggested_adjustment": "none",
    "news_risk": "none",
    "trade_pattern_note": "none",
}


def get_verdict(context: str, api_key: str) -> dict:
    """Send context to Claude and return parsed JSON verdict."""
    client = anthropic.Anthropic(api_key=api_key)

    user_msg = (
        f"Here is the current market context and signal data:\n\n{context}\n\n"
        "Respond with your verdict in the required JSON format."
    )

    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = message.content[0].text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        verdict = json.loads(raw)
        _validate_verdict(verdict)
        return verdict

    except json.JSONDecodeError as exc:
        log.error("Claude returned invalid JSON: %s", exc)
        return FALLBACK
    except anthropic.APIError as exc:
        log.error("Anthropic API error: %s", exc)
        return FALLBACK
    except Exception as exc:
        log.error("Unexpected error in analyst: %s", exc)
        return FALLBACK


def _validate_verdict(v: dict) -> None:
    required = {"verdict", "confidence", "reasoning", "key_levels",
                 "risk_flags", "suggested_adjustment", "news_risk", "trade_pattern_note"}
    missing = required - set(v.keys())
    if missing:
        raise ValueError(f"Missing keys in verdict: {missing}")

    valid_verdicts    = {"GO", "NO-GO", "CAUTION"}
    valid_confidence  = {"HIGH", "MEDIUM", "LOW"}
    valid_adjustments = {"none", "reduce_lot", "widen_sl", "tighten_sl"}
    valid_news        = {"none", "low", "high"}

    if v["verdict"] not in valid_verdicts:
        raise ValueError(f"Invalid verdict: {v['verdict']}")
    if v["confidence"] not in valid_confidence:
        raise ValueError(f"Invalid confidence: {v['confidence']}")
    if v["suggested_adjustment"] not in valid_adjustments:
        raise ValueError(f"Invalid adjustment: {v['suggested_adjustment']}")
    if v["news_risk"] not in valid_news:
        raise ValueError(f"Invalid news_risk: {v['news_risk']}")


if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    logging.basicConfig(level=logging.INFO)

    sample_context = """=== INDICATOR SNAPSHOT ===
Timeframe: 1H
  EMA21: 1912.0 | EMA50: 1905.0 | Trend: BULLISH
  ADX: 27.3 | ATR: 2.1

Timeframe: 5m
  BB Upper: 1916.0 | BB Mid: 1912.0 | BB Lower: 1908.0
  RSI: 44.2 | Prev RSI: 41.0 | RSI Direction: TURNING UP
  ATR: 1.8 | ATR Avg(20): 1.4

=== SIGNAL ===
Direction: BUY
Entry: 1913.0 | SL: 1909.5 | TP: 1921.75 | SL Dist: 3.5 pts
BE Level: 1914.8 | Lot: 0.01
Session: London | Regime: trend

=== ECONOMIC CALENDAR (±2 hours) ===
No high-impact events in the next 2 hours.

=== RECENT TRADES (Last 5) ===
No recent trades available."""

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("Set ANTHROPIC_API_KEY to test live call")
        sys.exit(0)

    result = get_verdict(sample_context, api_key)
    print(json.dumps(result, indent=2))
