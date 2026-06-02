#!/usr/bin/env python3
import sqlite3
import yaml
import json
from datetime import datetime, timedelta

config = yaml.safe_load(open('/opt/analyzer/config/config.yaml'))
db_path = config['database']['stock']
tickers = config['stock']['tickers']

def get_db():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def score_technical(ticker, conn):
    """Score based on RSI, MACD, Bollinger Bands"""
    c = conn.cursor()
    c.execute('''
        SELECT close, rsi, macd, signal_line, bb_upper, bb_lower
        FROM price_history
        WHERE ticker = ?
        ORDER BY timestamp DESC
        LIMIT 3
    ''', (ticker,))
    rows = c.fetchall()
    if not rows:
        return 50, {}

    latest = rows[0]
    score = 50
    factors = {}

    # RSI scoring
    rsi = latest['rsi']
    if rsi:
        if rsi < 30:
            score += 20
            factors['rsi'] = f'Oversold ({rsi:.1f}) — strong buy signal'
        elif rsi < 45:
            score += 10
            factors['rsi'] = f'Below neutral ({rsi:.1f}) — mildly bullish'
        elif rsi < 55:
            score += 0
            factors['rsi'] = f'Neutral ({rsi:.1f})'
        elif rsi < 70:
            score -= 5
            factors['rsi'] = f'Above neutral ({rsi:.1f}) — mildly bearish'
        else:
            score -= 15
            factors['rsi'] = f'Overbought ({rsi:.1f}) — caution'

    # MACD scoring
    macd = latest['macd']
    signal = latest['signal_line']
    if macd and signal:
        gap = macd - signal
        if len(rows) >= 2:
            prev_gap = (rows[1]['macd'] or 0) - (rows[1]['signal_line'] or 0)
            # Bullish crossover
            if prev_gap < 0 and gap > 0:
                score += 20
                factors['macd'] = 'Bullish crossover — strong signal'
            # Bearish crossover
            elif prev_gap > 0 and gap < 0:
                score -= 20
                factors['macd'] = 'Bearish crossover — warning'
            elif gap > 0:
                score += 10
                factors['macd'] = f'Bullish momentum (gap: {gap:.2f})'
            else:
                score -= 10
                factors['macd'] = f'Bearish momentum (gap: {gap:.2f})'

    # Bollinger Bands scoring
    close = latest['close']
    bb_upper = latest['bb_upper']
    bb_lower = latest['bb_lower']
    if close and bb_upper and bb_lower:
        bb_range = bb_upper - bb_lower
        bb_position = (close - bb_lower) / bb_range if bb_range > 0 else 0.5
        if bb_position < 0.2:
            score += 15
            factors['bollinger'] = f'Near lower band — oversold'
        elif bb_position > 0.8:
            score -= 15
            factors['bollinger'] = f'Near upper band — overbought'
        elif bb_position < 0.4:
            score += 5
            factors['bollinger'] = f'Lower half of bands — mild bullish'
        else:
            score += 0
            factors['bollinger'] = f'Middle of bands — neutral'

    return max(0, min(100, score)), factors

def score_volume(ticker, conn):
    """Score based on volume patterns"""
    c = conn.cursor()
    c.execute('''
        SELECT timestamp, close, volume, avg_volume_20d, volume_ratio
        FROM price_history
        WHERE ticker = ?
        ORDER BY timestamp DESC
        LIMIT 20
    ''', (ticker,))
    rows = c.fetchall()
    if not rows:
        return 50, {}

    score = 50
    factors = {}
    latest = rows[0]

    # Recent volume ratio
    vol_ratio = latest['volume_ratio']
    if vol_ratio:
        if vol_ratio > 2.0:
            score += 20
            factors['volume'] = f'Breakout volume ({vol_ratio:.1f}x average)'
        elif vol_ratio > 1.3:
            score += 10
            factors['volume'] = f'Elevated volume ({vol_ratio:.1f}x average)'
        elif vol_ratio < 0.5:
            score -= 5
            factors['volume'] = f'Low volume ({vol_ratio:.1f}x average)'
        else:
            factors['volume'] = f'Normal volume ({vol_ratio:.1f}x average)'

    # Check for accumulation pattern
    # High volume on up days, low volume on down days
    up_volume = 0
    down_volume = 0
    for i in range(min(10, len(rows)-1)):
        curr = rows[i]
        prev = rows[i+1]
        if curr['close'] > prev['close']:
            up_volume += curr['volume'] or 0
        else:
            down_volume += curr['volume'] or 0

    if up_volume + down_volume > 0:
        accumulation_ratio = up_volume / (up_volume + down_volume)
        if accumulation_ratio > 0.65:
            score += 15
            factors['accumulation'] = f'Accumulation pattern ({accumulation_ratio:.0%} up volume)'
        elif accumulation_ratio < 0.35:
            score -= 15
            factors['accumulation'] = f'Distribution pattern ({accumulation_ratio:.0%} up volume)'
        else:
            factors['accumulation'] = f'Neutral volume distribution'

    # Short volume ratio trend
    c.execute('''
        SELECT timestamp, short_volume_ratio
        FROM short_volume
        WHERE ticker = ?
        ORDER BY timestamp DESC
        LIMIT 5
    ''', (ticker,))
    sv_rows = c.fetchall()
    if sv_rows:
        latest_sv = sv_rows[0]['short_volume_ratio']
        if latest_sv:
            if latest_sv < 35:
                score += 15
                factors['short_volume'] = f'Very low short ratio ({latest_sv:.1f}%) — heavy buying'
            elif latest_sv < 45:
                score += 5
                factors['short_volume'] = f'Low short ratio ({latest_sv:.1f}%) — mild buying'
            elif latest_sv > 60:
                score -= 10
                factors['short_volume'] = f'High short ratio ({latest_sv:.1f}%) — heavy shorting'
            else:
                factors['short_volume'] = f'Normal short ratio ({latest_sv:.1f}%)'

    return max(0, min(100, score)), factors

def score_short_squeeze(ticker, conn):
    """Score short squeeze potential"""
    c = conn.cursor()
    c.execute('''
        SELECT timestamp, short_interest, days_to_cover, avg_daily_volume
        FROM short_interest
        WHERE ticker = ?
        ORDER BY timestamp DESC
        LIMIT 3
    ''', (ticker,))
    rows = c.fetchall()
    if not rows:
        return 50, {}

    score = 50
    factors = {}
    latest = rows[0]

    # Days to cover
    days_to_cover = latest['days_to_cover']
    if days_to_cover:
        if days_to_cover > 5:
            score += 25
            factors['days_to_cover'] = f'Very high squeeze risk ({days_to_cover:.1f} days to cover)'
        elif days_to_cover > 3:
            score += 15
            factors['days_to_cover'] = f'High squeeze risk ({days_to_cover:.1f} days to cover)'
        elif days_to_cover > 1.5:
            score += 5
            factors['days_to_cover'] = f'Moderate squeeze risk ({days_to_cover:.1f} days to cover)'
        else:
            score -= 5
            factors['days_to_cover'] = f'Low squeeze risk ({days_to_cover:.1f} days to cover)'

    # Short interest trend
    if len(rows) >= 2:
        curr_si = latest['short_interest'] or 0
        prev_si = rows[1]['short_interest'] or 0
        if prev_si > 0:
            si_change = ((curr_si - prev_si) / prev_si) * 100
            if si_change > 20:
                score += 10
                factors['si_trend'] = f'Short interest building (+{si_change:.1f}%) — squeeze risk rising'
            elif si_change < -20:
                score -= 10
                factors['si_trend'] = f'Short interest declining ({si_change:.1f}%) — squeeze risk falling'
            else:
                factors['si_trend'] = f'Short interest stable ({si_change:+.1f}%)'

    return max(0, min(100, score)), factors

def score_macro(conn):
    """Score macro environment for growth stocks"""
    c = conn.cursor()

    indicators = {}
    for indicator in ['vix', 'fed_funds_rate', 'treasury_10yr', 'oil_price_wti', 'yield_curve']:
        c.execute('''
            SELECT value, change_pct
            FROM macro_data
            WHERE indicator = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (indicator,))
        row = c.fetchone()
        if row:
            indicators[indicator] = dict(row)

    score = 50
    factors = {}

    # VIX — fear gauge
    if 'vix' in indicators:
        vix = indicators['vix']['value']
        if vix < 15:
            score += 15
            factors['vix'] = f'Low fear (VIX {vix:.1f}) — bullish environment'
        elif vix < 20:
            score += 5
            factors['vix'] = f'Normal fear (VIX {vix:.1f})'
        elif vix < 30:
            score -= 10
            factors['vix'] = f'Elevated fear (VIX {vix:.1f}) — caution'
        else:
            score -= 25
            factors['vix'] = f'High fear (VIX {vix:.1f}) — bearish environment'

    # Fed funds rate trend
    if 'fed_funds_rate' in indicators:
        change = indicators['fed_funds_rate']['change_pct'] or 0
        rate = indicators['fed_funds_rate']['value']
        if change < -0.1:
            score += 10
            factors['fed'] = f'Fed cutting rates ({rate:.2f}%) — bullish for growth'
        elif change > 0.1:
            score -= 10
            factors['fed'] = f'Fed hiking rates ({rate:.2f}%) — bearish for growth'
        else:
            factors['fed'] = f'Fed rates stable ({rate:.2f}%)'

    # 10yr yield
    if 'treasury_10yr' in indicators:
        yield_10yr = indicators['treasury_10yr']['value']
        if yield_10yr > 4.5:
            score -= 10
            factors['yield'] = f'High 10yr yield ({yield_10yr:.2f}%) — pressure on growth stocks'
        elif yield_10yr < 3.5:
            score += 10
            factors['yield'] = f'Low 10yr yield ({yield_10yr:.2f}%) — supportive for growth'
        else:
            factors['yield'] = f'Moderate 10yr yield ({yield_10yr:.2f}%)'

    # Yield curve
    if 'yield_curve' in indicators:
        curve = indicators['yield_curve']['value']
        if curve > 0.5:
            score += 10
            factors['yield_curve'] = f'Normal yield curve ({curve:.2f}%) — no recession signal'
        elif curve < 0:
            score -= 15
            factors['yield_curve'] = f'Inverted yield curve ({curve:.2f}%) — recession warning'
        else:
            factors['yield_curve'] = f'Flat yield curve ({curve:.2f}%)'

    return max(0, min(100, score)), factors

def score_momentum(ticker, conn):
    """Score price momentum"""
    c = conn.cursor()
    c.execute('''
        SELECT timestamp, close
        FROM price_history
        WHERE ticker = ?
        ORDER BY timestamp DESC
        LIMIT 50
    ''', (ticker,))
    rows = c.fetchall()
    if len(rows) < 20:
        return 50, {}

    score = 50
    factors = {}

    current_price = rows[0]['close']

    # 20-day average
    avg_20 = sum(r['close'] for r in rows[:20]) / 20
    pct_vs_20 = ((current_price - avg_20) / avg_20) * 100
    if pct_vs_20 > 5:
        score += 15
        factors['vs_20d'] = f'Price {pct_vs_20:.1f}% above 20-day avg — strong momentum'
    elif pct_vs_20 > 0:
        score += 5
        factors['vs_20d'] = f'Price {pct_vs_20:.1f}% above 20-day avg'
    elif pct_vs_20 > -5:
        score -= 5
        factors['vs_20d'] = f'Price {pct_vs_20:.1f}% below 20-day avg'
    else:
        score -= 15
        factors['vs_20d'] = f'Price {pct_vs_20:.1f}% below 20-day avg — weak momentum'

    # 50-day average
    if len(rows) >= 50:
        avg_50 = sum(r['close'] for r in rows[:50]) / 50
        pct_vs_50 = ((current_price - avg_50) / avg_50) * 100
        if pct_vs_50 > 10:
            score += 15
            factors['vs_50d'] = f'Price {pct_vs_50:.1f}% above 50-day avg — strong uptrend'
        elif pct_vs_50 > 0:
            score += 5
            factors['vs_50d'] = f'Price {pct_vs_50:.1f}% above 50-day avg'
        elif pct_vs_50 > -10:
            score -= 5
            factors['vs_50d'] = f'Price {pct_vs_50:.1f}% below 50-day avg'
        else:
            score -= 15
            factors['vs_50d'] = f'Price {pct_vs_50:.1f}% below 50-day avg — downtrend'

    # 5-day momentum
    pct_5d = ((rows[0]['close'] - rows[4]['close']) / rows[4]['close']) * 100
    if pct_5d > 5:
        score += 10
        factors['momentum_5d'] = f'Strong 5-day momentum (+{pct_5d:.1f}%)'
    elif pct_5d < -5:
        score -= 10
        factors['momentum_5d'] = f'Weak 5-day momentum ({pct_5d:.1f}%)'
    else:
        factors['momentum_5d'] = f'5-day momentum: {pct_5d:+.1f}%'

    return max(0, min(100, score)), factors

def generate_signal(ticker):
    conn = get_db()

    print(f"\n{'='*50}")
    print(f"SIGNAL REPORT: {ticker}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    # Get current price
    c = conn.cursor()
    c.execute('''
        SELECT close, timestamp FROM price_history
        WHERE ticker = ? ORDER BY timestamp DESC LIMIT 1
    ''', (ticker,))
    price_row = c.fetchone()
    if price_row:
        print(f"Last Price: ${price_row['close']:.2f} ({price_row['timestamp']})")

    # Score each component
    tech_score, tech_factors = score_technical(ticker, conn)
    vol_score, vol_factors = score_volume(ticker, conn)
    squeeze_score, squeeze_factors = score_short_squeeze(ticker, conn)
    macro_score, macro_factors = score_macro(conn)
    momentum_score, momentum_factors = score_momentum(ticker, conn)

    # Weighted combined score
    combined = (
        tech_score * 0.25 +
        vol_score * 0.20 +
        squeeze_score * 0.25 +
        macro_score * 0.15 +
        momentum_score * 0.15
    )

    # Signal classification
    if combined >= 70:
        signal = 'STRONG BUY SETUP'
        signal_emoji = '🟢🟢'
    elif combined >= 60:
        signal = 'BUY SETUP'
        signal_emoji = '🟢'
    elif combined >= 50:
        signal = 'WATCH'
        signal_emoji = '🟡'
    elif combined >= 40:
        signal = 'HOLD'
        signal_emoji = '⚪'
    elif combined >= 30:
        signal = 'SELL SETUP'
        signal_emoji = '🔴'
    else:
        signal = 'STRONG SELL SETUP'
        signal_emoji = '🔴🔴'

    print(f"\n{signal_emoji} SIGNAL: {signal}")
    print(f"Combined Score: {combined:.1f}/100")

    print(f"\n--- Component Scores ---")
    print(f"Technical:     {tech_score:.0f}/100 (25% weight)")
    print(f"Volume:        {vol_score:.0f}/100 (20% weight)")
    print(f"Short Squeeze: {squeeze_score:.0f}/100 (25% weight)")
    print(f"Macro:         {macro_score:.0f}/100 (15% weight)")
    print(f"Momentum:      {momentum_score:.0f}/100 (15% weight)")

    print(f"\n--- Key Factors ---")
    all_factors = {**tech_factors, **vol_factors,
                   **squeeze_factors, **macro_factors, **momentum_factors}
    for key, value in all_factors.items():
        print(f"  {key}: {value}")

    # Store signal in database
    c.execute('''INSERT OR REPLACE INTO signals
        (timestamp, ticker, signal, confidence,
        technical_score, sentiment_score, combined_score)
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ticker,
            signal,
            int(combined),
            tech_score,
            squeeze_score,
            combined
        )
    )
    conn.commit()
    conn.close()

    return combined, signal

# Generate signals for all tickers
for ticker in tickers:
    generate_signal(ticker)

print("\nSignal generation complete")
