#!/usr/bin/env python3
import sqlite3
import time
import yaml
from datetime import datetime, timedelta
from dotenv import dotenv_values
from fredapi import Fred

config = yaml.safe_load(open('/opt/analyzer/config/config.yaml'))
env = dotenv_values('/opt/analyzer/config/.env')

FRED_API_KEY = env.get('FRED_API_KEY')
db_path = config['database']['stock']

fred = Fred(api_key=FRED_API_KEY)

# FRED series to fetch
# Each tuple: (series_id, indicator_name, description)
INDICATORS = [
    ('FEDFUNDS',  'fed_funds_rate',    'Federal Funds Rate'),
    ('DGS10',     'treasury_10yr',     '10-Year Treasury Yield'),
    ('DGS2',      'treasury_2yr',      '2-Year Treasury Yield'),
    ('DCOILWTICO','oil_price_wti',      'WTI Crude Oil Price'),
    ('CPIAUCSL',  'cpi',               'Consumer Price Index'),
    ('UNRATE',    'unemployment',       'Unemployment Rate'),
    ('GDP',       'gdp',               'Gross Domestic Product'),
    ('VIXCLS',    'vix',               'CBOE Volatility Index'),
    ('DTWEXBGS',  'dollar_index',      'US Dollar Index'),
    ('T10Y2Y',    'yield_curve',       '10Y-2Y Yield Curve Spread'),
]

def fetch_indicator(series_id, indicator_name, description):
    print(f"Fetching {description}...")

    try:
        # Fetch last 10 years of data
        start_date = '2022-01-01'
        end_date = datetime.today().strftime('%Y-%m-%d')

        series = fred.get_series(
            series_id,
            observation_start=start_date,
            observation_end=end_date
        )

        if series.empty:
            print(f"No data for {indicator_name}")
            return

        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        stored = 0

        prev_value = None
        for timestamp, value in series.items():
            if value != value:  # NaN check
                continue

            change_pct = None
            if prev_value is not None and prev_value != 0:
                change_pct = round(((value - prev_value) / prev_value) * 100, 4)

            c.execute('''INSERT OR REPLACE INTO macro_data
                (timestamp, indicator, value, change_pct, source)
                VALUES (?, ?, ?, ?, ?)''',
                (
                    timestamp.strftime('%Y-%m-%d'),
                    indicator_name,
                    round(float(value), 4),
                    change_pct,
                    'FRED'
                )
            )
            stored += 1
            prev_value = value

        conn.commit()
        conn.close()
        print(f"{indicator_name}: {stored} records stored")

    except Exception as e:
        print(f"Error fetching {indicator_name}: {e}")

for series_id, indicator_name, description in INDICATORS:
    fetch_indicator(series_id, indicator_name, description)
    time.sleep(1)

print("Macro fetch complete")