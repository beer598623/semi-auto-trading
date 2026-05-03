"""Generate XAUUSD MTF BB Pullback v2.5 system spec PDF using reportlab."""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from datetime import date

OUTPUT = "/home/user/semi-auto-trading/XAUUSD_System_Spec.pdf"

# ── Colours
GOLD  = colors.HexColor("#B48C28")
DARK  = colors.HexColor("#1E1E1E")
LGRAY = colors.HexColor("#F0F0F0")
DGRAY = colors.HexColor("#5A5A5A")
BLUE  = colors.HexColor("#1E50A0")
RED   = colors.HexColor("#B42828")
WHITE = colors.white


def build():
    doc = SimpleDocTemplate(
        OUTPUT, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=20*mm, bottomMargin=20*mm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    def S(name, parent="Normal", **kw):
        return ParagraphStyle(name, parent=styles[parent], **kw)

    title_s    = S("Title2",   fontSize=22, textColor=GOLD, backColor=DARK,
                   alignment=TA_CENTER, spaceAfter=4, spaceBefore=4,
                   fontName="Helvetica-Bold", leading=28)
    sub_s      = S("Sub2",     fontSize=12, textColor=WHITE, backColor=DARK,
                   alignment=TA_CENTER, spaceAfter=2, fontName="Helvetica")
    section_s  = S("Sec",      fontSize=11, textColor=GOLD, backColor=DARK,
                   fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=3,
                   leading=16, leftIndent=4)
    subsec_s   = S("Subsec",   fontSize=10, textColor=BLUE,
                   fontName="Helvetica-Bold", spaceBefore=4, spaceAfter=2)
    body_s     = S("Body2",    fontSize=9,  leading=14)
    mono_s     = S("Mono",     fontSize=8.5, fontName="Courier",
                   backColor=colors.HexColor("#111111"),
                   textColor=GOLD, leading=13, leftIndent=6)
    note_s     = S("Note",     fontSize=8.5, textColor=DGRAY, fontName="Helvetica-Oblique")
    red_s      = S("Red",      fontSize=8.5, textColor=RED)

    story = []

    def section(title):
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph(f"&nbsp;&nbsp;{title}", section_s))

    def subsection(title):
        story.append(Paragraph(title, subsec_s))

    def body(text):
        story.append(Paragraph(text.replace("\n", "<br/>"), body_s))

    def kv_table(rows, col_widths=(55*mm, 120*mm)):
        data = [[Paragraph(f"<b>{k}</b>", body_s), Paragraph(v, body_s)] for k, v in rows]
        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("VALIGN",      (0,0), (-1,-1), "TOP"),
            ("ROWBACKGROUNDS", (0,0), (-1,-1), [LGRAY, WHITE]),
            ("LEFTPADDING",  (0,0), (-1,-1), 4),
            ("RIGHTPADDING", (0,0), (-1,-1), 4),
            ("TOPPADDING",   (0,0), (-1,-1), 3),
            ("BOTTOMPADDING",(0,0), (-1,-1), 3),
        ]))
        story.append(t)

    def rules_table(rows):
        data = [["#", "Condition", "Note"]] + list(rows)
        t = Table(data, colWidths=[8*mm, 115*mm, 52*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,0), DARK),
            ("TEXTCOLOR",    (0,0), (-1,0), GOLD),
            ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",     (0,0), (-1,-1), 8.5),
            ("ROWBACKGROUNDS",(0,1),(-1,-1), [LGRAY, WHITE]),
            ("LEFTPADDING",  (0,0), (-1,-1), 4),
            ("TOPPADDING",   (0,0), (-1,-1), 3),
            ("BOTTOMPADDING",(0,0), (-1,-1), 3),
            ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ]))
        story.append(t)

    # ── Cover ────────────────────────────────────────────────────────────────
    story.append(Paragraph("XAUUSD MTF BB Pullback v2.5", title_s))
    story.append(Paragraph("System Specification &amp; Overview", sub_s))
    story.append(Paragraph(f"Generated {date.today().strftime('%d %B %Y')}", note_s))
    story.append(HRFlowable(width="100%", thickness=1, color=GOLD, spaceAfter=6))

    # ── 1. Overview ───────────────────────────────────────────────────────────
    section("1. SYSTEM OVERVIEW")
    kv_table([
        ("Instrument",   "XAU/USD — Gold vs US Dollar"),
        ("System Type",  "MTF BB Pullback — Semi-auto Signal Generator"),
        ("Broker",       "Exness MT5"),
        ("Account",      "$100  |  Risk per trade: 1% ($1.00)"),
        ("Tech Stack",   "GitHub Actions + TwelveData API + Claude Sonnet 4.6 + Telegram + Notion"),
    ])

    # ── 2. Timeframe Structure ────────────────────────────────────────────────
    section("2. TIMEFRAME STRUCTURE")
    subsection("Trend Timeframe — 1H")
    body("EMA21 vs EMA50 → defines BULLISH / BEARISH direction<br/>"
         "ADX(10) ≥ 22.0 → confirms trend strength<br/>"
         "|EMA21−EMA50| / EMA50 > 0.1% → rejects flat / sideways market")
    story.append(Spacer(1, 3*mm))
    subsection("Entry Timeframe — 5m")
    body("BB(20, 2.0) → identifies price overextension at band extremes<br/>"
         "RSI(14) → confirms momentum direction is turning<br/>"
         "ATR(14) → measures volatility; used for SL, TP, lot size, and activity filter")

    # ── 3. Indicator Parameters ───────────────────────────────────────────────
    section("3. INDICATOR PARAMETERS")
    kv_table([
        ("Bollinger Bands", "Period = 20  |  StdDev = 2.0"),
        ("RSI",             "Period = 14"),
        ("ATR",             "Period = 14"),
        ("EMA",             "Fast = 21  |  Slow = 50"),
        ("ADX",             "Period = 10"),
        ("Regime",          "Trend if ADX ≥ 25  |  Range if ADX < 25"),
    ])

    # ── 4. Signal Conditions ──────────────────────────────────────────────────
    section("4. SIGNAL CONDITIONS")
    subsection("BUY Signal — all 8 conditions must be true")
    rules_table([
        ("1", "1H: EMA21 > EMA50",                         "Bullish trend"),
        ("2", "1H: ADX ≥ 22.0",                            "Strong trend"),
        ("3", "1H: |EMA21−EMA50| / EMA50 > 0.1%",         "Not flat"),
        ("4", "5m: prev_low < BB_lower",                   "Breached lower band"),
        ("5", "5m: current_close > BB_lower",              "Closed back inside"),
        ("6", "5m: prev_RSI < 48  AND  RSI > prev_RSI",   "Momentum turning up"),
        ("7", "5m: ATR ≥ ATR_avg_20bar × 1.2",            "Market active"),
        ("8", "SL distance ≤ 3.0 × ATR",                  "SL not too wide"),
    ])
    story.append(Spacer(1, 4*mm))
    subsection("SELL Signal — all 8 conditions must be true")
    rules_table([
        ("1", "1H: EMA21 < EMA50",                         "Bearish trend"),
        ("2", "1H: ADX ≥ 22.0",                            "Strong trend"),
        ("3", "1H: |EMA21−EMA50| / EMA50 > 0.1%",         "Not flat"),
        ("4", "5m: prev_high > BB_upper",                  "Breached upper band"),
        ("5", "5m: current_close < BB_upper",              "Closed back inside"),
        ("6", "5m: prev_RSI > 52  AND  RSI < prev_RSI",   "Momentum turning down"),
        ("7", "5m: ATR ≥ ATR_avg_20bar × 1.2",            "Market active"),
        ("8", "SL distance ≤ 3.0 × ATR",                  "SL not too wide"),
    ])

    # ── 5. Risk Management ────────────────────────────────────────────────────
    section("5. RISK MANAGEMENT")
    kv_table([
        ("Risk/Trade",     "1% of account balance  ($1.00 on $100 account)"),
        ("Lot formula",    "floor(balance×0.01 / (SL_dist×100) / 0.01)×0.01  |  min 0.01"),
        ("BUY SL",         "prev_low − 0.3 × ATR"),
        ("SELL SL",        "prev_high + 0.3 × ATR"),
        ("Max SL",         "SL distance ≤ 3.0 × ATR  (signal rejected if wider)"),
        ("Take Profit",    "Entry ± 2.5 × SL distance  →  Risk:Reward = 1 : 2.5"),
        ("Break-even",     "Entry ± 1.0 × ATR"),
        ("Signal expiry",  "10 minutes time-based  OR  0.5 × ATR price-based"),
    ])

    # ── 6. Auto-Skip Filters ──────────────────────────────────────────────────
    section("6. AUTO-SKIP FILTERS")
    kv_table([
        ("Weekend",        "Saturday all day  |  Sunday all day  |  Friday 23:00+ UTC"),
        ("Rollover",       "21:59 – 22:10 UTC daily"),
        ("Session guard",  "Active only 06:00 – 18:00 UTC  (London + New York sessions)"),
        ("Loss streak",    "Pause if ≥ 3 consecutive losses TODAY (UTC)  →  auto-resets next day"),
        ("Weak trend",     "Skip if ADX < 22.0"),
        ("Low volatility", "Skip if ATR < ATR_avg × 1.2"),
        ("Flat market",    "Skip if EMA spread < 0.1%"),
    ])

    # ── 7. System Flow ────────────────────────────────────────────────────────
    section("7. SYSTEM FLOW")
    flow_rows = [
        ["GitHub Actions  (cron: Mon–Fri 06:00 UTC & 12:00 UTC)"],
        ["fetch_ohlcv.py  →  1H 55 bars + 5m 55 bars  via TwelveData API"],
        ["fetch_calendar.py  →  ForexFactory USD High-impact events ±2 hours"],
        ["signal_filter.py  →  Rule-based check (8 conditions per direction)"],
        ["  FAIL → log NO_SIGNAL → sleep 300s → next iteration"],
        ["  PASS → context_builder.py → format structured context"],
        ["analyst.py  →  Claude Sonnet 4.6 API  →  parse JSON verdict"],
        ["telegram.py  →  send formatted signal alert"],
        ["notion.py  →  create page in Notion database"],
    ]
    t = Table([[Paragraph(r[0], body_s)] for r in flow_rows], colWidths=[175*mm])
    t.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [LGRAY, WHITE]),
        ("LEFTPADDING",    (0,0), (-1,-1), 8),
        ("TOPPADDING",     (0,0), (-1,-1), 3),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 3),
    ]))
    story.append(t)

    # ── 8. Claude AI Role ─────────────────────────────────────────────────────
    section("8. CLAUDE AI ROLE")
    body("Claude acts as <b>Senior Quantitative Strategist for XAUUSD</b>. "
         "Receives full context: indicators, 1H×20 bars + 5m×50 bars price action, "
         "economic calendar (±2 hrs), and recent trade history.")
    story.append(Spacer(1, 3*mm))
    kv_table([
        ("Model",               "claude-sonnet-4-6  |  max_tokens: 1000"),
        ("verdict",             "GO / NO-GO / CAUTION"),
        ("confidence",          "HIGH / MEDIUM / LOW"),
        ("reasoning",           "2–3 sentence price action analysis"),
        ("key_levels",          "Important price levels to watch"),
        ("risk_flags",          "Identified risks (news, structure, etc.)"),
        ("suggested_adjustment","none / reduce_lot / widen_sl / tighten_sl"),
        ("news_risk",           "none / low / high"),
        ("Fallback",            "Invalid JSON or API error → treated as NO-GO automatically"),
    ])

    # ── 9. GitHub Actions Schedule ────────────────────────────────────────────
    section("9. GITHUB ACTIONS SCHEDULE")
    kv_table([
        ("Trigger",        "Cron Mon–Fri + manual workflow_dispatch"),
        ("Job 1",          "06:00 UTC  (13:00 Thailand)  →  London session open"),
        ("Job 2",          "12:00 UTC  (19:00 Thailand)  →  NY session open"),
        ("Runtime",        "355 minutes per job  (~6 hours continuous)"),
        ("Loop interval",  "Every 300 seconds (5 minutes)"),
        ("Coverage",       "London 06–12 UTC  +  NY 12–18 UTC"),
    ])

    # ── 10. Notion Schema ─────────────────────────────────────────────────────
    section("10. NOTION DATABASE SCHEMA")
    body("<b>Database ID:</b> be871b32ef3549068c9d3dea76d3fbca")
    story.append(Spacer(1, 3*mm))
    subsection("Auto-filled by bot:")
    auto = [
        ["Signal",            "Title",  "'{DIR} @ {entry} | {timestamp}'"],
        ["Timestamp",         "Date",   "UTC datetime"],
        ["Direction",         "Select", "BUY / SELL"],
        ["Entry / SL / TP",   "Number", "Price values"],
        ["SL Dist / Lot",     "Number", "Calculated"],
        ["Session",           "Select", "London / NY / NY_Late / Asia"],
        ["Regime",            "Select", "trend / range"],
        ["ADX / RSI / ATR",   "Number", "Indicator snapshot"],
        ["Claude Verdict",    "Select", "GO / NO-GO / CAUTION"],
        ["Claude Confidence", "Select", "HIGH / MEDIUM / LOW"],
        ["Claude Reasoning",  "Text",   "AI analysis"],
        ["Claude Risk Flags", "Text",   "Comma-separated"],
        ["Claude Adjustment", "Select", "none / reduce_lot / widen_sl / tighten_sl"],
        ["News Risk",         "Select", "none / low / high"],
        ["Action",            "Select", "CONFIRM (default auto)"],
    ]
    t = Table([["Field", "Type", "Value"]] + auto,
              colWidths=[48*mm, 22*mm, 105*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), DARK),
        ("TEXTCOLOR",     (0,0), (-1,0), GOLD),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8.5),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [LGRAY, WHITE]),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(t)
    story.append(Spacer(1, 3*mm))
    subsection("Fill manually after each trade:")
    manual = [
        ["Action",        "Select", "CONFIRM / SKIP / EXPIRED"],
        ["Actual Entry",  "Number", "Real fill price"],
        ["Exit Price",    "Number", "Closing price"],
        ["PnL",           "Number", "Profit/Loss in USD"],
        ["Hold Time Min", "Number", "Minutes position was held"],
    ]
    t2 = Table([["Field", "Type", "Value"]] + manual,
               colWidths=[48*mm, 22*mm, 105*mm])
    t2.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), RED),
        ("TEXTCOLOR",     (0,0), (-1,0), WHITE),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8.5),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.HexColor("#FFF0F0"), WHITE]),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(t2)

    # ── 11. Future Optimization Notes ────────────────────────────────────────
    section("11. FUTURE OPTIMIZATION NOTES")
    notes = [
        ("ADX threshold",        "22.0 → raise to 25+ for stronger trend-only entries"),
        ("RSI thresholds",       "48/52 → tighten for more selective entries"),
        ("ATR multiplier",       "1.2× → increase to filter low-volatility chop"),
        ("TP ratio",             "2.5R → backtest 2.0R vs 3.0R for win-rate vs expectancy"),
        ("BB parameters",        "20/2.0 → try 14/1.5 for higher signal frequency"),
        ("Session filter",       "Narrow to London open 06–09 UTC for cleanest setups"),
        ("MT5 integration",      "Windows VPS + MetaTrader5 Python lib for auto-execution"),
        ("Loss streak logic",    "Consider equity-based pause instead of count-based"),
        ("Multi-instrument",     "Extend to EURUSD / GBPUSD with same framework"),
    ]
    kv_table(notes)

    doc.build(story)
    print(f"PDF saved: {OUTPUT}")


if __name__ == "__main__":
    build()
