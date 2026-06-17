#!/usr/bin/env python3
import sqlite3
import yaml
import feedparser
import requests
from datetime import datetime, timedelta
from dotenv import dotenv_values

config = yaml.safe_load(open('/opt/analyzer/config/config.yaml'))
db_path = config['database']['stock']

# Free RSS feeds for macro news
RSS_FEEDS = [
    ('https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml', 'economy'),
    ('https://rss.nytimes.com/services/xml/rss/nyt/Business.xml', 'business'),
    ('https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml', 'tech_sentiment'),
    ('https://feeds.a.dj.com/rss/RSSMarketsMain.xml', 'markets'),
    ('https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml', 'business'),
    ('https://feeds.a.dj.com/rss/RSSWSJD.xml', 'markets'),
    ('https://www.cnbc.com/id/10000664/device/rss/rss.html', 'economy'),
    ('https://www.cnbc.com/id/10001147/device/rss/rss.html', 'tech_sentiment'),
    ('https://feeds.bloomberg.com/markets/news.rss', 'markets'),
    ('https://www.federalreserve.gov/feeds/press_all.xml', 'fed_policy'),
]

# Keywords to classify topics
TOPIC_KEYWORDS = {
    'fed_policy': ['federal reserve', 'fed', 'interest rate', 'powell', 'fomc', 'monetary policy'],
    'inflation': ['inflation', 'cpi', 'consumer price', 'pce', 'deflation'],
    'employment': ['jobs', 'unemployment', 'nonfarm', 'payroll', 'labor market'],
    'gdp': ['gdp', 'economic growth', 'recession', 'contraction'],
    'oil': ['oil', 'crude', 'opec', 'energy price', 'wti', 'brent'],
    'china': ['china', 'chinese economy', 'trade war', 'tariff', 'beijing'],
    'geopolitical': ['war', 'conflict', 'sanctions', 'geopolitical', 'middle east', 'ukraine'],
    'ai_sentiment': ['artificial intelligence', 'ai market', 'nvidia', 'chatgpt', 'llm'],
    'tech_sentiment': ['tech stocks', 'nasdaq', 'growth stocks', 'rate hike tech'],
    'dollar': ['dollar index', 'usd', 'currency', 'forex', 'strong dollar'],
    'bonds': ['treasury yield', 'bond yield', '10-year', 'yield curve'],
    'semiconductors': ['semiconductor', 'chip', 'tsmc', 'supply chain'],
}

def classify_topic(title, description):
    """Classify article into a macro topic"""
    text = (title + ' ' + description).lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return topic
    return None

def fetch_rss_news():
    print("Fetching macro news from RSS feeds...")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    stored = 0
    cutoff = (datetime.today() - timedelta(days=7)).strftime('%Y-%m-%d')

    for feed_url, default_topic in RSS_FEEDS:
        print(f"Fetching: {feed_url}...")
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                description = entry.get('summary', '')
                published = entry.get('published', '')

                # Parse date
                try:
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6]).strftime('%Y-%m-%d')
                    else:
                        pub_date = datetime.today().strftime('%Y-%m-%d')
                except:
                    pub_date = datetime.today().strftime('%Y-%m-%d')

                # Skip old articles
                if pub_date < cutoff:
                    continue

                # Classify topic
                topic = classify_topic(title, description) or default_topic
                source = feed.feed.get('title', feed_url)

                c.execute('''INSERT OR IGNORE INTO macro_news
                    (timestamp, headline, source, topic, sentiment, reasoning)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                    (pub_date, title, source, topic, None, description)
                )

                stored += 1

        except Exception as e:
            print(f" Error fetching {feed_url}: {e}")

    conn.commit()
    conn.close()
    print(f"Macro News: {stored} articles stored")

fetch_rss_news()
print("Macro news fetch complete")