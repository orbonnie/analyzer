import sqlite3
import yaml

print("Starting...")

with open('/opt/analyzer/config/config.yaml') as f:
    config = yaml.safe_load(f)

db_path = config['database']['stock']
print(f"DB path: {db_path}")

conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER, rsi REAL, macd REAL,
    signal_line REAL, bb_upper REAL, bb_lower REAL,
    UNIQUE(ticker, timestamp)
)''')

c.execute('''CREATE TABLE IF NOT EXISTS news_sentiment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    headline TEXT, source TEXT, ticker TEXT,
    sentiment TEXT, confidence INTEGER,
    affected_sectors TEXT, time_horizon TEXT, reasoning TEXT
)''')

c.execute('''CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ticker TEXT, signal TEXT, confidence INTEGER,
    technical_score REAL, sentiment_score REAL, combined_score REAL
)''')

c.execute('''CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT UNIQUE NOT NULL,
    name TEXT, sector TEXT, added_date TEXT, notes TEXT
)''')

c.execute('CREATE INDEX IF NOT EXISTS idx_price_ticker ON price_history(ticker)')
c.execute('CREATE INDEX IF NOT EXISTS idx_price_timestamp ON price_history(timestamp)')
c.execute('CREATE INDEX IF NOT EXISTS idx_news_ticker ON news_sentiment(ticker)')
c.execute('CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals(ticker)')

conn.commit()
conn.close()
print('Stock database initialized successfully')
