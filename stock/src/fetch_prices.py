#!/usr/bin/env python3
import sqlite3
import yaml
import pandas as pd
from datetime import datetime, timedelta
from dotenv import dotenv_values
from massive import RESTClient

# Load config and API key
config = yaml.safe_load(open('/opt/analyzer/config/config.yaml'))
env = dotenv_values('/opt/analyzer/config/.env')

API_KEY = env.get('MASSIVE_API_KEY')
db_path = config['database']['stock']
tickers = config['stock']['tickers']

# Initialize Massive client
client = RESTClient(API_KEY)

def calculate_indicators(df):
    # RSI
    delta = df['close'].diff()
    gain = delta.clip(lower=0).rolling(window=14).mean()
    loss = (-delta).clip(lower=0).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['signal_line'] = df['macd'].ewm(span=9, adjust=False).mean()

    # Bollinger Bands
    sma20 = df['close'].rolling(window=20).mean()
    std20 = df['close'].rolling(window=20).std()
    df['bb_upper'] = sma20 + (std20 * 2)
    df['bb_lower'] = sma20 - (std20 * 2)

    return df


def fetch_and_store(ticker):
    print(f"Fetching {ticker}...")

    try:
        end_date = datetime.today().strftime('%Y-%m-%d')
        start_date = (datetime.today() - timedelta(days=90)).strftime('%Y-%m-%d')

        aggs = []
        for agg in client.list_aggs(
            ticker=ticker,
            multiplier=1,
            timespan="day",
            from_=start_date,
            to=end_date,
            limit=90
        ):
            aggs.append({
                'timestamp': datetime.fromtimestamp(agg.timestamp / 1000).strftime('%Y-%m-%d'),
                'open': round(agg.open, 2),
                'high': round(agg.high, 2),
                'low': round(agg.low, 2),
                'close': round(agg.close, 2),
                'volume': int(agg.volume)
            })

        if not aggs:
            print(f"No data for {ticker}")
            return

        # Build dataframe and calculate indicators
        df = pd.DataFrame(aggs)
        df = calculate_indicators(df)

        print(f"{ticker}: {len(df)} records with indicators calculated")

        # Store in database
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        for _, row in df.iterrows():
            c.execute('''INSERT OR REPLACE INTO price_history
                (ticker, timestamp, open, high, low, close, volume,
                rsi, macd, signal_line, bb_upper, bb_lower)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    ticker,
                    row['timestamp'],
                    row['open'],
                    row['high'],
                    row['low'],
                    row['close'],
                    row['volume'],
                    round(row['rsi'], 2) if pd.notna(row['rsi']) else None,
                    round(row['macd'], 4) if pd.notna(row['macd']) else None,
                    round(row['signal_line'], 4) if pd.notna(row['signal_line']) else None,
                    round(row['bb_upper'], 2) if pd.notna(row['bb_upper']) else None,
                    round(row['bb_lower'], 2) if pd.notna(row['bb_lower']) else None,
                )
            )

        conn.commit()
        conn.close()
        print(f"{ticker}: stored successfully")

    except Exception as e:
        print(f"Error fetching {ticker}: {e}")

for ticker in tickers:
    fetch_and_store(ticker)

print("Price fetch complete")
