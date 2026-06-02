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

# Ticker to CIK mapping
TICKER_CIKS = {
    'TWLO': '0001447669',
    'TSLA': '0001318605',
    'AAPL': '0000320193'
}

# Transaction codes
TRANSACTION_CODES = {
    'P': 'Purchase',
    'S': 'Sale',
    'A': 'Award',
    'F': 'Tax withholding',
    'M': 'Option exercise',
    'G': 'Gift',
    'D': 'Sale to issuer'
}

def fetch_insider_trades(ticker):
    print(f"Fetching insider trades for {ticker}...")

    cik = TICKER_CIKS.get(ticker)
    if not cik:
        print(f"No CIK found for {ticker}")
        return

    end_date = datetime.today().strftime('%Y-%m-%d')
    start_date = (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%d')

    url = 'https://api.polygon.io/stocks/filings/vX/form-4'
    params = {
        'issuer_cik': cik,
        'filing_date.gte': start_date,
        'filing_date.lte': end_date,
        'record_type': 'transaction',
        'limit': 1000,
        'sort': 'filing_date.desc',
        'apiKey': API_KEY
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if 'results' not in data:
            print(f"No results for {ticker}: {data.get('status')}")
            return

        results = data['results']
        print(f"{ticker}: {len(results)} insider transactions found")

        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        stored = 0

        for r in results:
            # Skip non-equity transactions
            if r.get('security_type') != 'non_derivative':
                continue

            c.execute('''INSERT OR IGNORE INTO insider_trades
                (ticker, filing_date, transaction_date, owner_name,
                officer_title, is_director, is_officer, transaction_code,
                transaction_shares, transaction_price, transaction_value,
                shares_owned_after, acquired_disposed, is_10b5_plan, record_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    ticker,
                    r.get('filing_date'),
                    r.get('transaction_date'),
                    r.get('owner_name'),
                    r.get('officer_title'),
                    1 if r.get('is_director') else 0,
                    1 if r.get('is_officer') else 0,
                    r.get('transaction_code'),
                    r.get('transaction_shares'),
                    r.get('transaction_price_per_share'),
                    r.get('transaction_value'),
                    r.get('shares_owned_following_transaction'),
                    r.get('transaction_acquired_disposed'),
                    1 if r.get('aff_10b5_one') else 0,
                    r.get('record_type')
                )
            )
            stored += 1

        conn.commit()
        conn.close()
        print(f"{ticker}: {stored} transactions stored")

    except Exception as e:
        print(f"Error fetching insider trades for {ticker}: {e}")

for ticker in TICKER_CIKS:
    fetch_insider_trades(ticker)

print("Insider fetch complete")
