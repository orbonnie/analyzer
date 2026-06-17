#!/usr/bin/env python3
import sqlite3
import yaml
import json
import requests
from datetime import datetime

config = yaml.safe_load(open('/opt/analyzer/config/config.yaml'))
db_path = config['database']['stock']
tickers = config['stock']['tickers']

OLLAMA_URL = 'http://localhost:11434/api/generate'
MODEL = 'phi4-mini'

DRY_RUN = True

def analyze_sentiment(headline, reasoning, ticker):
    prompt = f"""Analyze this news headline and its impact on {ticker} stock.
Headline: {headline}
Context: {reasoning[:200] if reasoning else ''}

Sentiment MUST be exactly ONE of:
- "positive"
- "negative"
- "neutral"

DO NOT use any other values such as "mixed", "slightly positive", etc.


Return JSON in this exact schema:
{{
  "sentiment": "positive" | "negative" | "neutral",
  "confidence": number (0-100),
  "impact": "immediate" | "short_term" | "long_term",
  "reasoning": "one sentence explanation"
}}"""

    try:
        response = requests.post(OLLAMA_URL, json={
            'model': MODEL,
            'prompt': prompt,
            'stream': False
        })
        result = response.json()
        text = result.get('response', '').strip()

        # Parse JSON response
        # Clean up common issues
        text = text.replace('```json', '').replace('```', '').strip()
        data = json.loads(text)
        return data

    except Exception as e:
        return None


def apply_updates(results, dry_run=DRY_RUN):
    if dry_run:
        print("\n--- DRY RUN MODE (no DB changes) ---")

        for r in results:
            print(
                f"[DRY RUN] id={r['id']} | "
                f"sentiment={r['sentiment']} | "
                f"confidence={r['confidence']} | "
                f"impact={r['impact']}"
            )

        print(f"\nWould update {len(results)} rows\n")
        return

    if not results:
        print("No updates to apply.")
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    for r in results:
        c.execute('''
            UPDATE news_sentiment
            SET sentiment = ?,
                confidence = ?,
                time_horizon = ?,
                reasoning = ?
            WHERE id = ?
        ''', (
            r["sentiment"],
            r["confidence"],
            r["impact"],
            r["reasoning"],
            r["id"]
        ))

    conn.commit()
    conn.close()

    print(f"Applied {len(results)} updates to database")


def apply_updates_macro(results, dry_run=DRY_RUN):
    if dry_run:
        print("\n--- DRY RUN (macro) ---")
        for r in results:
            print(f"[DRY RUN] id={r['id']} sentiment={r['sentiment']}")
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    for r in results:
        c.execute('''
            UPDATE macro_news
            SET sentiment = ?,
                reasoning = ?
            WHERE id = ?
        ''', (
            r["sentiment"],
            r["reasoning"],
            r["id"]
        ))

    conn.commit()
    conn.close()

    print(f"Applied {len(results)} macro updates")


def score_ticker_news(ticker):
    print(f"Analyzing sentiment for {ticker}...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get unscored articles for this ticker
    c.execute('''
        SELECT id, headline, reasoning, sentiment
        FROM news_sentiment
        WHERE ticker = ?
        ORDER BY timestamp DESC
        LIMIT 50
    ''', (ticker,))

    rows = c.fetchall()
    print(f"{ticker}: {len(rows)} articles")

    results = []

    for row in rows:
        result = analyze_sentiment(row['headline'], row['reasoning'], ticker)
        if result and result.get("sentiment") != row['sentiment']:
            print( f"MASSIVE: {row['sentiment']}, REVISED: {result.get('sentiment')}, CONFIDENCE: {result.get('confidence')}")
            print( f"HEADLINE: {row['headline']}, MASS REASON: {row['reasoning']} AI REASON: {result.get('reasoning')}\n")
            results.append({
                "id": row["id"],
                "sentiment": result.get("sentiment"),
                "confidence": result.get("confidence"),
                "impact": result.get("impact"),
                "reasoning": result.get("reasoning"),
            })

            conn.close()

            # c.execute('''
            #     UPDATE news_sentiment
            #     SET sentiment = ?,
            #         confidence = ?,
            #         time_horizon = ?,
            #         reasoning = ?
            #     WHERE id = ?
            # ''', (
            #     result.get('sentiment'),
            #     result.get('confidence'),
            #     result.get('impact'),
            #     result.get('reasoning'),
            #     row['id']
            # ))

    apply_updates(results, dry_run=DRY_RUN)


def score_macro_news():
    print("Analyzing macro news sentiment...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute('''
        SELECT id, headline, reasoning, topic
        FROM macro_news
        ORDER BY timestamp DESC
        LIMIT 100
    ''')
    rows = c.fetchall()
    print(f"Macro: {len(rows)} unscored articles")

    results = []
    for row in rows:
        # For macro news analyze impact on growth stocks generally
        result = analyze_sentiment(
            row['headline'],
            row['reasoning'],
            'growth stocks'
        )

        if result:
            if result:
                results.append({
                    "id": row["id"],
                    "sentiment": result.get("sentiment"),
                    "confidence": result.get("confidence"),
                    "impact": result.get("impact"),
                    "reasoning": result.get("reasoning"),
                })

            # c.execute('''
            #     UPDATE macro_news
            #     SET sentiment = ?,
            #         reasoning = ?
            #     WHERE id = ?
            # ''', (
            #     result.get('sentiment'),
            #     result.get('reasoning'),
            #     row['id']
            # ))

    conn.close()

    apply_updates_macro(results, dry_run=DRY_RUN)


# Score ticker news
for ticker in tickers:
    score_ticker_news(ticker)

# Score macro news
score_macro_news()

print("Sentiment analysis complete")