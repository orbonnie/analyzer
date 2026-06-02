#!/usr/bin/env python3
import sqlite3
import yaml
import requests
from datetime import datetime, timedelta
from dotenv import dotenv_values

config = yaml.safe_load(open('/opt/analyzer/config/config.yaml'))
env = dotenv_values('/opt/analyzer/config/.env')

API_KEY = env.get('MASSIVE_API_KEY')
db_path = config['database']['stock']
tickers = config['stock']['tickers']

def fetch_short_interest(ticker):
    print(f"Fetching short interest for {ticker}...")

    # Date range - last 6 months
    end_date = datetime.today().strftime('%Y-%m-%d')
    start_date = (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%d')

    url = "https://api.massive.com/stocks/v1/short-interest"
    params = {
        'ticker': ticker,
        'settlement_date.gte': start_date,
        'settlement_date.lte': end_date,
        'limit': 50,
        'sort': 'settlement_date.desc',
        'apiKey': API_KEY
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        print(f"Status: {data.get('status')}")

        if 'results' not in data:
            print(f"No results: {data}")
            return

        results = data['results']
        print(f"{ticker}: {len(results)} short interest records found")

        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        stored = 0

        for record in results:
            c.execute('''INSERT OR REPLACE INTO short_interest
                (ticker, timestamp, short_interest,
                short_interest_pct_float, days_to_cover, avg_daily_volume)
                VALUES (?, ?, ?, ?, ?, ?)''',
                (
                    record.get('ticker', ticker),
                    record.get('settlement_date', ''),
                    record.get('short_interest'),
                    None,  # not provided by this endpoint
                    record.get('days_to_cover'),
                    record.get('avg_daily_volume')
                )
            )
            stored += 1

        conn.commit()
        conn.close()
        print(f"{ticker}: {stored} records stored")

    except Exception as e:
        print(f"Error fetching short interest for {ticker}: {e}")

for ticker in tickers:
    fetch_short_interest(ticker)

print("Short interest fetch complete")
