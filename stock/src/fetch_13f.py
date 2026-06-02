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

def init_13f_table():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS institutional_holdings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        filer_cik TEXT,
        filer_name TEXT,
        filing_date TEXT,
        period TEXT,
        shares INTEGER,
        market_value INTEGER,
        UNIQUE(ticker, filer_cik, period)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS institutional_changes (
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
    c.execute('CREATE INDEX IF NOT EXISTS idx_inst_ticker ON institutional_holdings(ticker)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_inst_change_ticker ON institutional_changes(ticker)')
    conn.commit()
    conn.close()
    print("13F tables initialized")

def fetch_13f_for_ticker(ticker):
    print(f"Fetching 13F data for {ticker}...")

    # Get last 2 quarters
    end_date = datetime.today().strftime('%Y-%m-%d')
    start_date = (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%d')

    url = 'https://api.polygon.io/stocks/filings/vX/13-F'
    params = {
        'ticker': ticker,
        'filing_date.gte': start_date,
        'filing_date.lte': end_date,
        'limit': 1000,
        'apiKey': API_KEY
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if 'results' not in data:
            print(f"No 13F results for {ticker}: {data.get('status')}")
            return

        results = data['results']
        print(f"{ticker}: {len(results)} 13F records found")

        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        # Group by filer and period
        holdings = {}
        for record in results:
            key = (record.get('filer_cik'), record.get('period'))
            if key not in holdings:
                holdings[key] = {
                    'filer_cik': record.get('filer_cik'),
                    'filing_date': record.get('filing_date'),
                    'period': record.get('period'),
                    'shares': 0,
                    'market_value': 0
                }
            holdings[key]['shares'] += record.get('shares_or_principal_amount', 0)
            holdings[key]['market_value'] += record.get('market_value', 0)

        print(f"{ticker}: {len(holdings)} unique filers found")

        # Store holdings
        for (filer_cik, period), data in holdings.items():
            c.execute('''INSERT OR REPLACE INTO institutional_holdings
                (ticker, filer_cik, filing_date, period, shares, market_value)
                VALUES (?, ?, ?, ?, ?, ?)''',
                (ticker, filer_cik, data['filing_date'],
                period, data['shares'], data['market_value'])
            )

        conn.commit()

        # Calculate quarter over quarter changes
        print(f"Calculating QoQ changes for {ticker}...")
        c.execute('''
            SELECT h1.filer_cik, h1.period as curr_period,
                   h2.period as prev_period,
                   h2.shares as prev_shares,
                   h1.shares as curr_shares,
                   h1.shares - h2.shares as change_shares,
                   round(((h1.shares - h2.shares) * 100.0 / h2.shares), 2) as change_pct
            FROM institutional_holdings h1
            JOIN institutional_holdings h2
                ON h1.ticker = h2.ticker
                AND h1.filer_cik = h2.filer_cik
                AND h1.period > h2.period
            WHERE h1.ticker = ?
            ORDER BY change_pct DESC
        ''', (ticker,))

        changes = c.fetchall()
        print(f"{ticker}: {len(changes)} QoQ changes calculated")

        for change in changes:
            filer_cik, curr_period, prev_period, prev_shares, curr_shares, change_shares, change_pct = change
            c.execute('''INSERT OR REPLACE INTO institutional_changes
                (ticker, filer_cik, period, prev_period,
                prev_shares, curr_shares, change_shares, change_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (ticker, filer_cik, curr_period, prev_period,
                prev_shares, curr_shares, change_shares, change_pct)
            )

        conn.commit()
        conn.close()
        print(f"{ticker}: 13F data stored successfully")

    except Exception as e:
        print(f"Error fetching 13F for {ticker}: {e}")

init_13f_table()

for ticker in tickers:
    fetch_13f_for_ticker(ticker)

print("13F fetch complete")