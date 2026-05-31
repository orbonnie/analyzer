#!/usr/bin/env python3
import sqlite3
import yaml
import requests
from datetime import datetime, timedelta
from dotenv import dotenv_values


# Load config and API key
config = yaml.safe_load(open('/opt/analyzer/config/config.yaml'))
env = dotenv_values('/opt/analyzer/config/.env')
API_KEY = env.get('MASSIVE_API_KEY')
db_path = config['database']['stock']
tickers = config['stock']['tickers']


def fetch_news_for_ticker(ticker):
    print(f"Fetching {ticker}...")

    # Date range - last 7 days
    end_date = datetime.today().strftime('%Y-%m-%d')
    start_date = (datetime.today() - timedelta(days=7)).strftime('%Y-%m-%d')

    url = f"https://api.polygon.io/v2/reference/news"
    params = {
        'ticker': ticker,
        'published_utc.gte': start_date,
        'published_utc.lte': end_date,
        'limit': 50,
        'sort': 'published_utc',
        'order': 'desc',
        'apiKey': API_KEY
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if 'results' not in data:
            print(f"Noe news for {ticker}: {data}")
            return

        articles = data['results']
        print(f"{ticker}: {len(articles)} articles found")

        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        stored = 0

        for article in articles:
            # Extract relevant fields
            published = article.get('published_utc', '')[:10]
            headline = article.get('title', '')
            source = article.get('publisher', {}).get('name', '')
            url = article.get('article_url', '')
            description = article.get('description', '')

            # Extract ticker-specific sentiment from insights
            sentiment = None
            reasoning = description
            for insight in article.get('insights', []):
                if insight.get('ticker') == ticker:
                    sentiment = insight.get('sentiment')
                    reasoning = insight.get('sentiment_reasoning', description)
                    break

            c.execute('''INSERT OR IGNORE INTO news_sentiment
                (timestamp, headline, source, ticker, sentiment,
                confidence, affected_sectors, time_horizon, reasoning)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    published,
                    headline,
                    source,
                    ticker,
                    sentiment,
                    None,  # confidence
                    None,  # affected_sectors
                    None,  # time_horizon
                    reasoning
                )
            )
            stored += 1

        conn.commit()
        conn.close()
        print(f"{ticker}: {stored} articles stored")

    except Exception as e:
        print(f"Error fetching news for {ticker}: {e}")

for ticker in tickers:
    fetch_news_for_ticker(ticker)

print("News fetch complete")
