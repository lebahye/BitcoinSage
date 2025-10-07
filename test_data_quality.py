#!/usr/bin/env python
import datetime
import pytz
import yfinance as yf

# Current time
now_utc = datetime.datetime.now(pytz.UTC)
now_et = now_utc.astimezone(pytz.timezone('US/Eastern'))

print('=== CURRENT TIME & MARKET STATUS ===')
print(f'Current time ET: {now_et.strftime("%Y-%m-%d %H:%M:%S %Z")}')
print(f'Day: {now_et.strftime("%A")}')

# Check market hours
weekday = now_et.weekday()
hour = now_et.hour
minute = now_et.minute
is_weekday = weekday < 5
is_market_hours = (hour == 9 and minute >= 30) or (10 <= hour < 16)
market_open = is_weekday and is_market_hours

print(f'Market is: {"OPEN" if market_open else "CLOSED"}')
print()

# Test RIOT data freshness
print('=== RIOT DATA FRESHNESS TEST ===')
ticker = yf.Ticker('RIOT')
info = ticker.info

# Get last trade time
last_trade_ts = info.get('regularMarketTime', 0)
if last_trade_ts:
    last_trade = datetime.datetime.fromtimestamp(last_trade_ts, tz=pytz.timezone('US/Eastern'))
    delay = now_et - last_trade
    print(f'Last RIOT trade: {last_trade.strftime("%Y-%m-%d %H:%M:%S %Z")}')
    print(f'Data age: {delay}')
    print(f'Hours old: {delay.total_seconds() / 3600:.1f}')
    
    # Quality assessment
    hours_old = delay.total_seconds() / 3600
    if hours_old > 24:
        print('❌ DATA QUALITY: TERRIBLE (>24 hours old)')
    elif hours_old > 4:
        print('⚠️ DATA QUALITY: POOR (>4 hours old)')  
    elif hours_old > 0.5:
        print('⚠️ DATA QUALITY: STALE (>30 min old)')
    else:
        print('✅ DATA QUALITY: GOOD (recent)')
else:
    print('ERROR: No timestamp available')

print(f'Current RIOT price: ${info.get("regularMarketPrice", "ERROR")}')
print()

# Check historical data
print('=== HISTORICAL DATA TEST ===')
hist = ticker.history(period='1d', interval='5m')
if not hist.empty:
    last_candle = hist.index[-1]
    print(f'Latest 5min candle: {last_candle}')
    print(f'Candle close: ${hist["Close"].iloc[-1]:.2f}')
    candle_age = now_et - last_candle.tz_convert('US/Eastern')
    print(f'Candle age: {candle_age}')
else:
    print('ERROR: No historical data')

print()

# Check options data
print('=== OPTIONS DATA TEST (Your $25 Nov Calls) ===')
try:
    options_dates = ticker.options
    if options_dates:
        print(f'Available expirations: {len(options_dates)} dates')
        
        # Find November options
        nov_calls = [d for d in options_dates if '2025-11' in d]
        if nov_calls:
            print(f'November expirations: {nov_calls}')
            nov_chain = ticker.option_chain(nov_calls[0])
            strike_25 = nov_chain.calls[nov_chain.calls['strike'] == 25.0]
            if not strike_25.empty:
                print(f'\n$25 Nov 21 Call (Your Position):')
                print(f'  Last Price: ${strike_25.iloc[0]["lastPrice"]}')
                print(f'  Bid: ${strike_25.iloc[0]["bid"]}')
                print(f'  Ask: ${strike_25.iloc[0]["ask"]}')
                print(f'  Volume: {strike_25.iloc[0]["volume"]}')
                print(f'  Open Interest: {strike_25.iloc[0]["openInterest"]}')
                
                # Compare to what you paid
                your_price = 1.05
                current_price = strike_25.iloc[0]["lastPrice"]
                diff = current_price - your_price
                pct_change = (diff / your_price) * 100
                print(f'\n  You sold at: ${your_price}')
                print(f'  Current price: ${current_price}')
                print(f'  Change: ${diff:.2f} ({pct_change:+.1f}%)')
                
                if diff < 0:
                    print(f'  ✅ Profitable to buy back (cheaper now)')
                else:
                    print(f'  ⚠️ More expensive now (wait or roll)')
            else:
                print('WARNING: $25 strike not found')
except Exception as e:
    print(f'OPTIONS ERROR: {e}')

print('\n=== DATA SOURCE ASSESSMENT ===')
print('Current data source: Yahoo Finance (yfinance)')
print('Real-time capability: ❌ NO - Delayed 15+ min to hours')
print('Schwab API status: Not configured')
print('\n⚠️ RECOMMENDATION: Set up Schwab API for real-time data')
