from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
PAPER_BASE_URL = "https://paper-api.alpaca.markets"

PROJECT_ROOT = Path(__file__).resolve().parents[4]
BOT_ROOT = PROJECT_ROOT / "bot"
DEFAULT_ENV_FILE = PROJECT_ROOT / "config" / ".env"
LOGS_DIR = PROJECT_ROOT / "logs"
BACKTESTS_DIR = PROJECT_ROOT / "backtests"
STATE_DIR = BOT_ROOT / "state"
STATE_FILE = STATE_DIR / "state.json"
SIM_ACCOUNT_FILE = STATE_DIR / "sim_account.json"
BOT_LOG_FILE = STATE_DIR / "bot.log"
KILL_SWITCH_FILE = BOT_ROOT / "KILL"

# Strategy
BAR_MINUTES = 5
OPENING_RANGE_MINUTES = 15
DEFAULT_MARKET_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)
EARLY_CLOSE = time(13, 0)
DEFAULT_WATCHLIST = "SPY,QQQ,AAPL,MSFT,NVDA,TSLA,AMD,META,GOOGL,AMZN"
ENTRY_WINDOW_END = time(11, 0)
FLATTEN_MINUTES_BEFORE_CLOSE = 5
FLATTEN_RETRY_SECONDS = 20
TARGET_R_MULTIPLE = 2.0
MAX_GAP_PCT = 0.02
# Breakout bar volume vs. mean volume of the session's earlier bars.
MIN_VOLUME_MULTIPLE = 1.0

# Risk
RISK_PER_TRADE_PCT = 0.02
MAX_DAILY_LOSS_PCT = 0.06
MAX_WEEKLY_LOSS_PCT = 0.10
# 3 x RISK_PER_TRADE_PCT equals MAX_DAILY_LOSS_PCT, so a day of three full stops still ends exactly at the daily limit.
MAX_TRADES_PER_DAY = 3
MAX_POSITION_PCT = 0.25
# A razor-thin opening range would size into thousands of shares.
MIN_RISK_PER_SHARE = 0.05

# Runtime
POLL_SECONDS = 15
BAR_SETTLE_SECONDS = 10
CLIENT_ORDER_PREFIX = "orb"
BACKTEST_DATA_FEED = "sip"
ALPACA_BACKTEST_DAYS = 730
BENCHMARK_SAMPLES_PER_TRADE = 50
# Fixed seed so two backtests of the same data print the same benchmark.
BENCHMARK_SEED = 42

# Simulated broker
DEFAULT_SIM_STARTING_CASH = 10_000.0
# Market and stop orders fill this much worse than the bar price; limit targets fill exactly.
SIM_SLIPPAGE_PCT = 0.0005

# Yahoo Finance (unofficial, free)
YAHOO_HOSTS = ("query2.finance.yahoo.com", "query1.finance.yahoo.com")
YAHOO_USER_AGENT = "Mozilla/5.0 (compatible; orb-bot/0.1)"
YAHOO_TIMEOUT_SECONDS = 15
YAHOO_PAUSE_SECONDS = 0.5
YAHOO_RETRY_BACKOFF_SECONDS = 2.0
# Yahoo serves 5-minute bars for the last 60 days only.
YAHOO_BACKTEST_DAYS = 58

# News context in the journal
NEWS_LOOKBACK_HOURS = 24
NEWS_MAX_ITEMS_PER_SYMBOL = 5
YAHOO_RSS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FILINGS_URL = (
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=8-K"
    "&dateb=&owner=include&count=10&output=atom"
)
NEWS_TIMEOUT_SECONDS = 20
# SEC fair-access cap is 10 requests/second; stay well under it.
SEC_PAUSE_SECONDS = 0.15
