#!/usr/bin/env python3
import sqlite3
import yaml
import requests
import xml.etree.ElementTree as ET
import time
import json
from datetime import datetime, timedelta
from dotenv import dotenv_values

config = yaml.safe_load(open('/opt/analyzer/config/config.yaml'))
db_path = config['database']['stock']
tickers = config['stock']['tickers']

HEADERS = {'User-Agent': 'StockAnalyzer/1.0 bonnie@analyzer.com'}
NS = {'ns': 'http://www.sec.gov/edgar/document/thirteenf/informationtable'}

def init_tables():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
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
    c.execute('CREATE INDEX IF NOT EXISTS idx_inst_sec_ticker ON institutional_holdings_sec(ticker)')
    conn.commit()
    conn.close()
    print("Tables initialized")

def find_filers(ticker, max_filers=100):
    print(f"Finding 13F filers for {ticker}...")
    url = 'https://efts.sec.gov/LATEST/search-index'
    params = {
        'q': f'"Twilio"',
        'forms': '13F-HR',
        'dateRange': 'custom',
        'startdt': '2026-01-01',
        'enddt': datetime.today().strftime('%Y-%m-%d')
    }
    response = requests.get(url, params=params, headers=HEADERS)
    data = response.json()
    hits = data.get('hits', {}).get('hits', [])

    filers = {}
    for hit in hits:
        src = hit['_source']
        ciks = src.get('ciks', [])
        names = src.get('display_names', [])
        period = src.get('period_ending', '')
        filing_date = src.get('file_date', '')

        for i, cik in enumerate(ciks):
            name = names[i] if i < len(names) else ''
            if cik not in filers or period > filers[cik]['period']:
                filers[cik] = {
                    'name': name,
                    'period': period,
                    'filing_date': filing_date
                }

    print(f"{ticker}: {len(filers)} unique filers found")
    return filers

def get_filing_xml_url(cik, accession):
    accession_path = accession.replace('-', '')
    cik_int = str(int(cik))
    url = f'https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_path}/'
    response = requests.get(url, headers=HEADERS)
    time.sleep(0.15)  # respect SEC rate limit

    import re
    files = re.findall(r'href=\"(/Archives/edgar/data/[^\"]+\.(xml))\"', response.text)
    for f in files:
        if 'inftable' in f[0].lower() or 'infotable' in f[0].lower():
            return f'https://www.sec.gov{f[0]}'
    return None

def get_latest_accession(cik):
    url = f'https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json'
    response = requests.get(url, headers=HEADERS)
    time.sleep(0.15)

    data = response.json()
    filings = data.get('filings', {}).get('recent', {})
    forms = filings.get('form', [])
    accessions = filings.get('accessionNumber', [])
    dates = filings.get('filingDate', [])
    periods = filings.get('reportDate', [])

    # Get most recent 13F-HR
    for i, form in enumerate(forms):
        if form == '13F-HR':
            return accessions[i], dates[i], periods[i] if i < len(periods) else ''
    return None, None, None

def parse_holdings(xml_url, ticker):
    response = requests.get(xml_url, headers=HEADERS)
    time.sleep(0.15)

    if response.status_code != 200:
        return None

    try:
        root = ET.fromstring(response.text)
        holdings = root.findall('.//ns:infoTable', NS)

        for h in holdings:
            name = h.find('ns:nameOfIssuer', NS)
            shares = h.find('.//ns:sshPrnamt', NS)
            value = h.find('ns:value', NS)

            if name is not None and ticker.upper() in name.text.upper():
                return {
                    'shares': int(shares.text) if shares is not None else 0,
                    'market_value': int(value.text) if value is not None else 0
                }
    except ET.ParseError:
        return None
    return None

def fetch_institutional(ticker):
    print(f"\nFetching institutional holdings for {ticker}...")
    filers = find_filers(ticker)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    stored = 0

    for cik, info in list(filers.items())[:50]:  # limit to 50 filers
        try:
            # Get latest accession number
            accession, filing_date, period = get_latest_accession(cik)
            if not accession:
                continue

            # Get XML URL
            xml_url = get_filing_xml_url(cik, accession)
            if not xml_url:
                continue

            # Parse holdings
            holding = parse_holdings(xml_url, ticker)
            if not holding or holding['shares'] < 10000:
                continue

            # Store
            filer_name = info['name'].split('(CIK')[0].strip()
            c.execute('''INSERT OR REPLACE INTO institutional_holdings_sec
                (ticker, filer_cik, filer_name, filing_date, period, shares, market_value)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (ticker, cik, filer_name, filing_date, period,
                holding['shares'], holding['market_value'])
            )
            stored += 1
            print(f"  {filer_name}: {holding['shares']:,} shares")

        except Exception as e:
            print(f"  Error processing CIK {cik}: {e}")
            continue

    conn.commit()
    conn.close()
    print(f"{ticker}: {stored} institutional holders stored")

init_tables()

for ticker in tickers:
    fetch_institutional(ticker)

print("\nInstitutional fetch complete")