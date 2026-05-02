import os

TWELVEDATA_API_KEY = os.environ["TWELVEDATA_API_KEY"]
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
NOTION_TOKEN       = os.environ["NOTION_TOKEN"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
ACCOUNT_BALANCE    = float(os.environ.get("ACCOUNT_BALANCE", "100.0"))
RISK_PERCENT       = float(os.environ.get("RISK_PERCENT", "1.0"))
RUNTIME_MINUTES    = 355
LOOP_INTERVAL_SEC  = 300

# Indicator parameters
BB_PERIOD    = 20
BB_STDDEV    = 2.0
RSI_PERIOD   = 14
ATR_PERIOD   = 14
EMA_FAST     = 21
EMA_SLOW     = 50
ADX_PERIOD   = 10

# Signal thresholds
ADX_MIN           = 22.0
EMA_SPREAD_MIN    = 0.001   # 0.1%
ATR_MULT_MIN      = 1.2
RSI_BUY_MAX       = 48
RSI_SELL_MIN      = 52
SL_ATR_MULT_MAX   = 3.0
SL_ATR_BUFFER     = 0.3
TP_R_MULT         = 2.5
BE_ATR_MULT       = 1.0
SIGNAL_EXPIRY_MIN = 10

# Session guard (UTC)
SESSION_START_UTC = 6
SESSION_END_UTC   = 18

# Rollover window (UTC)
ROLLOVER_START = (21, 59)
ROLLOVER_END   = (22, 10)

# Loss streak pause threshold
MAX_LOSS_STREAK = 3
