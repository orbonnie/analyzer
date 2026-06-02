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

def fetch_short_volume(ticker):
    print(f"Fetching short volume for {ticker}...")

    end_date = datetime.today().strftime('%Y-%m-%d')
    start_date = (datetime.today() - timedelta(days=90)).strftime('%Y-%m-%d')

    url = 'https://api.massive.com/stocks/v1/short-volume'
    params = {
        'ticker': ticker,
        'date.gte': start_date,
        'date.lte': end_date,
        'limit': 90,
        'sort': 'date.desc',
        'apiKey': API_KEY
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if 'results' not in data:
            print(f"No results for {ticker}: {data.get('status')}")
            return

        results = data['results']
        print(f"{ticker}: {len(results)} short volume records found")

        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        stored = 0

        for r in results:
            c.execute('''INSERT OR REPLACE INTO short_volume
                (ticker, timestamp, short_volume, total_volume, short_volume_ratio)
                VALUES (?, ?, ?, ?, ?)''',
                (
                    ticker,
                    r.get('date'),
                    r.get('short_volume'),
                    r.get('total_volume'),
                    r.get('short_volume_ratio')
                )
            )
            stored += 1

        conn.commit()
        conn.close()
        print(f"{ticker}: {stored} records stored")

    except Exception as e:
        print(f"Error fetching short volume for {ticker}: {e}")

for ticker in tickers:
    fetch_short_volume(ticker)

print("Short volume fetch complete")
