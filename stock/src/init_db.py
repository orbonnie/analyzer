import sqlite3
import yaml

print("Starting...")

with open('/opt/analyzer/config/config.yaml') as f:
    config = yaml.safe_load(f)

db_path = config['database']['stock']
print(f"DB path: {db_path}")

conn = sqlite3.connect(db_path)
c = conn.cursor()

# Stock price history
c.execute('''CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    rsi REAL,
    macd REAL,
    signal_line REAL,
    bb_upper REAL,
    bb_lower REAL,
    avg_volume_20d REAL,
    volume_ratio REAL,
    UNIQUE(ticker, timestamp)
)''')

# News story sentiments
c.execute('''CREATE TABLE IF NOT EXISTS news_sentiment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    headline TEXT,
    source TEXT,
    ticker TEXT,
    sentiment TEXT,
    confidence INTEGER,
    affected_sectors TEXT,
    time_horizon TEXT,
    reasoning TEXT
)''')

# Technical signals
c.execute('''CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ticker TEXT, signal TEXT, confidence INTEGER,
    technical_score REAL, sentiment_score REAL, combined_score REAL
)''')

# Ticker watchlist
c.execute('''CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT UNIQUE NOT NULL,
    name TEXT,
    sector TEXT,
    added_date TEXT,
    notes TEXT
)''')

# Macro economic data
c.execute('''CREATE TABLE IF NOT EXISTS macro_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    indicator TEXT NOT NULL,
    value REAL,
    change_pct REAL,
    source TEXT,
    UNIQUE(timestamp, indicator)
)''')

# Macro events
c.execute('''CREATE TABLE IF NOT EXISTS macro_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    description TEXT,
    severity INTEGER,
    source TEXT
)''')

# Macro correlations
c.execute('''CREATE TABLE IF NOT EXISTS macro_correlations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    event_type TEXT NOT NULL,
    avg_1day_return REAL,
    avg_5day_return REAL,
    avg_30day_return REAL,
    std_deviation REAL,
    sample_count INTEGER,
    correlation_strength REAL,
    last_updated TEXT,
    UNIQUE(ticker, event_type)
)''')

# Macro signals
c.execute('''CREATE TABLE IF NOT EXISTS macro_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ticker TEXT NOT NULL,
    macro_score REAL,
    dominant_factors TEXT,
    historical_matches TEXT,
    predicted_1day REAL,
    predicted_5day REAL,
    predicted_30day REAL,
    confidence REAL
)''')

# Short interest
c.execute('''CREATE TABLE IF NOT EXISTS short_interest (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    short_interest INTEGER,
    short_interest_pct_float REAL,
    days_to_cover REAL,
    avg_daily_volume INTEGER,
    UNIQUE(ticker, timestamp)
)''')

# Short volume
c.execute('''CREATE TABLE IF NOT EXISTS short_volume (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    short_volume INTEGER,
    total_volume INTEGER,
    short_volume_ratio REAL,
    UNIQUE(ticker, timestamp)
)''')

# Macro news table
c.execute('''CREATE TABLE IF NOT EXISTS macro_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    headline TEXT,
    source TEXT,
    topic TEXT,
    sentiment TEXT,
    reasoning TEXT,
    UNIQUE(headline, timestamp)
)''')

# Insider trades
c.execute('''CREATE TABLE IF NOT EXISTS insider_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    filing_date TEXT,
    transaction_date TEXT,
    owner_name TEXT,
    officer_title TEXT,
    is_director INTEGER,
    is_officer INTEGER,
    transaction_code TEXT,
    transaction_shares REAL,
    transaction_price REAL,
    transaction_value REAL,
    shares_owned_after REAL,
    acquired_disposed TEXT,
    is_10b5_plan INTEGER,
    record_type TEXT,
    UNIQUE(ticker, owner_name, transaction_date, transaction_shares)
)''')

# Institutional holdings from SEC
c.execute('''CREATE TABLE IF NOT EXISTS institutional_holdings_sec (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    filer_cik TEXT NOT NULL,
    filer_name TEXT,
    filing_date TEXT,
    period TEXT,
    shares INTEGER,
    market_value INTEGER,
    UNIQUE(ticker, filer_cik, period)
)''')

# Institutional changes quarter over quarter
c.execute('''CREATE TABLE IF NOT EXISTS institutional_changes_sec (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    filer_cik TEXT,
    filer_name TEXT,
    period TEXT,
    prev_period TEXT,
    prev_shares INTEGER,
    curr_shares INTEGER,
    change_shares INTEGER,
    change_pct REAL,
    UNIQUE(ticker, filer_cik, period)
)''')

# Events calendar
c.execute('''CREATE TABLE IF NOT EXISTS events_calendar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    event_date TEXT NOT NULL,
    event_type TEXT NOT NULL,
    description TEXT,
    impact TEXT,
    source TEXT,
    UNIQUE(ticker, event_date, event_type)
)''')

c.execute('CREATE INDEX IF NOT EXISTS idx_price_ticker ON price_history(ticker)')
c.execute('CREATE INDEX IF NOT EXISTS idx_price_timestamp ON price_history(timestamp)')
c.execute('CREATE INDEX IF NOT EXISTS idx_news_ticker ON news_sentiment(ticker)')
c.execute('CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals(ticker)')
c.execute('CREATE INDEX IF NOT EXISTS idx_macro_indicator ON macro_data(indicator)')
c.execute('CREATE INDEX IF NOT EXISTS idx_macro_timestamp ON macro_data(timestamp)')
c.execute('CREATE INDEX IF NOT EXISTS idx_corr_ticker ON macro_correlations(ticker)')
c.execute('CREATE INDEX IF NOT EXISTS idx_short_ticker ON short_interest(ticker)')
c.execute('CREATE INDEX IF NOT EXISTS idx_shortvol_ticker ON short_volume(ticker)')
c.execute('CREATE INDEX IF NOT EXISTS idx_macro_news_topic ON macro_news(topic)')
c.execute('CREATE INDEX IF NOT EXISTS idx_macro_news_timestamp ON macro_news(timestamp)')
c.execute('CREATE INDEX IF NOT EXISTS idx_insider_ticker ON insider_trades(ticker)')
c.execute('CREATE INDEX IF NOT EXISTS idx_inst_sec_ticker ON institutional_holdings_sec(ticker)')
c.execute('CREATE INDEX IF NOT EXISTS idx_inst_change_ticker ON institutional_changes_sec(ticker)')
c.execute('CREATE INDEX IF NOT EXISTS idx_events_ticker ON events_calendar(ticker)')
c.execute('CREATE INDEX IF NOT EXISTS idx_events_date ON events_calendar(event_date)')

conn.commit()
conn.close()
print('Stock database initialized successfully')
