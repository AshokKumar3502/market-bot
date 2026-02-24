"""
🔍 UPSTOX API DEBUGGER
Run this first to find exactly what's failing before running the main bot.
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiIyQkNCNzQiLCJqdGkiOiI2OTliZGE5MTdmODBmOTFjMDgxNWM2YjgiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6dHJ1ZSwiaWF0IjoxNzcxODIxNzEzLCJpc3MiOiJ1ZGFwaS1nYXRld2F5LXNlcnZpY2UiLCJleHAiOjE3NzE4ODQwMDB9.XeGw4z7s9Hyqlsry3beozoqiLyUNP3l9ssqacyElKio"

TELEGRAM_BOT_TOKEN = "8539235085:AAH64vStKl89iWFVhJ06rvp4arsC7of51Bk"
CHAT_IDS = ["1336874504", "-1003655311849"]

TEST_STOCK = {"symbol": "DIXON", "instrument_key": "NSE_EQ|INE935N01020"}

# ─────────────────────────────────────────
# STEP 1: Token check
# ─────────────────────────────────────────
def test_token():
    print("\n" + "="*50)
    print("STEP 1: Testing Access Token...")
    print("="*50)
    url = "https://api.upstox.com/v2/user/profile"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Accept": "application/json"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"  Status Code : {r.status_code}")
        print(f"  Response    : {r.text[:300]}")
        if r.status_code == 200:
            u = r.json().get("data", {})
            print(f"  ✅ Token VALID — User: {u.get('user_name')} | Email: {u.get('email')}")
            return True
        elif r.status_code == 401:
            print("  ❌ Token EXPIRED or INVALID!")
            print("  👉 Go to https://upstox.com/developer/apps → regenerate token")
            return False
        else:
            print(f"  ⚠️  Unexpected status: {r.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Exception: {e}")
        return False

# ─────────────────────────────────────────
# STEP 2: Try fetching today's data
# ─────────────────────────────────────────
def test_fetch_today():
    print("\n" + "="*50)
    print("STEP 2: Fetching TODAY's 1-min data...")
    print("="*50)
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"  Today's date: {today}")
    print(f"  Current time: {datetime.now().strftime('%H:%M:%S')}")

    url = f"https://api.upstox.com/v2/historical-candle/{TEST_STOCK['instrument_key']}/1minute/{today}/{today}"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Accept": "application/json"}

    print(f"  URL: {url}")
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"  Status Code : {r.status_code}")

        if r.status_code != 200:
            print(f"  ❌ Error response: {r.text[:500]}")
            return None

        data = r.json()
        candles = data.get("data", {}).get("candles", [])
        print(f"  Candles returned: {len(candles)}")

        if len(candles) == 0:
            print("  ⚠️  ZERO candles returned for today!")
            print("  Possible reasons:")
            print("    1. Market is closed right now (check NSE trading hours: 9:15 AM - 3:30 PM IST)")
            print("    2. Today is a holiday/weekend")
            print("    3. Historical candle API doesn't return intraday data after market hours")
            return None
        else:
            print(f"  ✅ Got {len(candles)} candles")
            print(f"  First candle: {candles[-1]}")
            print(f"  Last  candle: {candles[0]}")
            return candles
    except Exception as e:
        print(f"  ❌ Exception: {e}")
        return None

# ─────────────────────────────────────────
# STEP 3: Try fetching yesterday's data (fallback test)
# ─────────────────────────────────────────
def test_fetch_yesterday():
    print("\n" + "="*50)
    print("STEP 3: Fetching YESTERDAY's 1-min data (to confirm API works)...")
    print("="*50)

    # Go back up to 5 days to find a trading day
    for days_back in range(1, 6):
        date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        url  = f"https://api.upstox.com/v2/historical-candle/{TEST_STOCK['instrument_key']}/1minute/{date}/{date}"
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Accept": "application/json"}

        print(f"  Trying date: {date}")
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                print(f"    Status {r.status_code}: {r.text[:200]}")
                continue
            candles = r.json().get("data", {}).get("candles", [])
            if candles:
                print(f"  ✅ Got {len(candles)} candles for {date}")
                print(f"  First candle: {candles[-1]}")
                print(f"  Last  candle: {candles[0]}")
                return date, candles
            else:
                print(f"    No candles for {date} (holiday/weekend?)")
        except Exception as e:
            print(f"    Exception: {e}")

    print("  ❌ Could not fetch any data for last 5 days")
    return None, None

# ─────────────────────────────────────────
# STEP 4: Try intraday API (alternative endpoint)
# ─────────────────────────────────────────
def test_intraday_api():
    print("\n" + "="*50)
    print("STEP 4: Trying INTRADAY candle API (better for live market)...")
    print("="*50)

    url = f"https://api.upstox.com/v2/historical-candle/intraday/{TEST_STOCK['instrument_key']}/1minute"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Accept": "application/json"}

    print(f"  URL: {url}")
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"  Status Code : {r.status_code}")
        if r.status_code != 200:
            print(f"  ❌ Error: {r.text[:300]}")
            return None
        candles = r.json().get("data", {}).get("candles", [])
        print(f"  Candles returned: {len(candles)}")
        if candles:
            print(f"  ✅ Intraday API works! Got {len(candles)} candles")
            print(f"  First candle: {candles[-1]}")
            print(f"  Last  candle: {candles[0]}")
            return candles
        else:
            print("  ⚠️  No intraday candles (market may be closed)")
            return None
    except Exception as e:
        print(f"  ❌ Exception: {e}")
        return None

# ─────────────────────────────────────────
# STEP 5: Test Telegram
# ─────────────────────────────────────────
def test_telegram():
    print("\n" + "="*50)
    print("STEP 5: Testing Telegram Bot...")
    print("="*50)
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for chat_id in CHAT_IDS:
        try:
            r = requests.post(url, data={
                "chat_id": chat_id,
                "text": f"🧪 <b>Bot Debug Test</b>\n✅ Telegram connection working!\n🕒 {datetime.now().strftime('%H:%M:%S')}",
                "parse_mode": "HTML"
            }, timeout=10)
            if r.status_code == 200:
                print(f"  ✅ Telegram OK for chat_id: {chat_id}")
            else:
                print(f"  ❌ Telegram FAILED for {chat_id}: {r.text}")
        except Exception as e:
            print(f"  ❌ Exception for {chat_id}: {e}")

# ─────────────────────────────────────────
# STEP 6: Full pipeline test on historical data
# ─────────────────────────────────────────
def test_full_pipeline(candles):
    print("\n" + "="*50)
    print("STEP 6: Testing Full Indicator Pipeline...")
    print("="*50)

    if not candles:
        print("  ⚠️  No candles to test with, skipping.")
        return

    # Upstox returns 6 or 7 columns depending on instrument (7th = open_interest)
    cols = ["datetime", "open", "high", "low", "close", "volume"]
    if candles and len(candles[0]) == 7:
        cols.append("oi")
        print(f"  ℹ️  API returned 7 columns (6 OHLCV + open_interest) — dropping OI column")
    df = pd.DataFrame(candles, columns=cols)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    print(f"  Raw 1-min bars  : {len(df)}")

    # 3-min resample
    df3 = df.resample("3T").agg({
        "open": "first", "high": "max",
        "low": "min", "close": "last", "volume": "sum"
    }).dropna()
    print(f"  3-min bars      : {len(df3)}")

    if len(df3) < 15:
        print(f"  ❌ Not enough 3-min bars ({len(df3)}). Need at least 15.")
        return

    # Heiken Ashi
    ha_close = (df3["open"] + df3["high"] + df3["low"] + df3["close"]) / 4
    ha_open  = [0.0] * len(df3)
    ha_open[0] = (df3["open"].iloc[0] + df3["close"].iloc[0]) / 2
    for i in range(1, len(df3)):
        ha_open[i] = (ha_open[i - 1] + ha_close.iloc[i - 1]) / 2
    ha_open_s = pd.Series(ha_open, index=df3.index)
    ha_high   = pd.concat([df3["high"], ha_open_s, ha_close], axis=1).max(axis=1)
    ha_low    = pd.concat([df3["low"],  ha_open_s, ha_close], axis=1).min(axis=1)
    ha = pd.DataFrame({
        "open": ha_open_s, "high": ha_high,
        "low": ha_low, "close": ha_close, "volume": df3["volume"]
    }, index=df3.index)
    print(f"  Heiken Ashi bars: {len(ha)}")

    # ATR RMA
    def rma(series, period):
        alpha  = 1.0 / period
        result = np.full(len(series), np.nan)
        vals   = series.values
        start  = next((i for i, v in enumerate(vals) if not np.isnan(v)), None)
        if start is None or start + period > len(vals):
            return pd.Series(result, index=series.index)
        result[start + period - 1] = np.nanmean(vals[start:start + period])
        for i in range(start + period, len(vals)):
            result[i] = alpha * vals[i] + (1 - alpha) * result[i - 1]
        return pd.Series(result, index=series.index)

    pc = ha["close"].shift(1)
    tr = pd.concat([
        ha["high"] - ha["low"],
        (ha["high"] - pc).abs(),
        (ha["low"]  - pc).abs()
    ], axis=1).max(axis=1)
    atr = rma(tr, 10)

    src       = (ha["high"] + ha["low"]) / 2
    raw_upper = (src + 3.0 * atr).values
    raw_lower = (src - 3.0 * atr).values
    close     = ha["close"].values
    n         = len(ha)

    upper      = np.full(n, np.nan)
    lower      = np.full(n, np.nan)
    direction  = np.full(n, np.nan)
    supertrend = np.full(n, np.nan)

    for i in range(n):
        if np.isnan(raw_upper[i]):
            continue
        if i == 0 or np.isnan(upper[i - 1]):
            upper[i] = raw_upper[i]; lower[i] = raw_lower[i]; direction[i] = 1
        else:
            lower[i] = raw_lower[i] if (raw_lower[i] > lower[i-1] or close[i-1] < lower[i-1]) else lower[i-1]
            upper[i] = raw_upper[i] if (raw_upper[i] < upper[i-1] or close[i-1] > upper[i-1]) else upper[i-1]
            if   close[i] > upper[i-1]: direction[i] =  1
            elif close[i] < lower[i-1]: direction[i] = -1
            else:                        direction[i] = direction[i-1]
        supertrend[i] = lower[i] if direction[i] == 1 else upper[i]

    ha["direction"]  = direction
    ha["supertrend"] = supertrend

    # Print last 5 bars
    print(f"\n  {'Time':<22} {'HA_Close':>10} {'Supertrend':>12} {'Direction':>10} {'Signal':>12}")
    print(f"  {'-'*70}")
    signals_found = []
    for i in range(max(0, n-10), n):
        t   = ha.index[i].strftime("%Y-%m-%d %H:%M")
        hac = round(float(ha["close"].iloc[i]), 2)
        st  = round(float(ha["supertrend"].iloc[i]), 2) if not np.isnan(ha["supertrend"].iloc[i]) else None
        d   = int(ha["direction"].iloc[i]) if not np.isnan(ha["direction"].iloc[i]) else None
        sig = ""
        if i > 0:
            pd_ = ha["direction"].iloc[i-1]
            cd_ = ha["direction"].iloc[i]
            if not np.isnan(pd_) and not np.isnan(cd_):
                if cd_ == 1 and pd_ == -1: sig = "BUY CALL 🟢"
                if cd_ == -1 and pd_ == 1: sig = "BUY PUT 🔴"
        if sig:
            signals_found.append((t, sig, hac))
        d_str  = ("BULL" if d == 1 else "BEAR") if d is not None else "N/A"
        st_str = str(st) if st else "N/A"
        print(f"  {t:<22} {hac:>10} {st_str:>12} {d_str:>10} {sig:>12}")

    last = ha.iloc[-1]
    curr_dir = "BULLISH 🟢" if last["direction"] == 1 else "BEARISH 🔴"
    print(f"\n  Current state  : {curr_dir}")
    print(f"  Current HA Close   : {round(float(last['close']), 2)}")
    print(f"  Current Supertrend : {round(float(last['supertrend']), 2)}")

    if signals_found:
        print(f"\n  ✅ Signals found in last 10 bars:")
        for t, sig, price in signals_found:
            print(f"    {t} → {sig} @ {price}")
    else:
        print(f"\n  ℹ️  No crossover in last 10 bars (trend is sustained {curr_dir})")
        print(f"     This is NORMAL — signals only fire when direction FLIPS.")
        print(f"     Your TradingView signal may have fired earlier today.")

# ─────────────────────────────────────────
# RUN ALL TESTS
# ─────────────────────────────────────────
print("="*50)
print("🔍 UPSTOX BOT DIAGNOSTIC TOOL")
print(f"   Running at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
print("="*50)

token_ok = test_token()

if token_ok:
    candles_today = test_fetch_today()
    candles_hist_date, candles_hist = test_fetch_yesterday()
    candles_intraday = test_intraday_api()

    # Use whichever has data
    candles_to_use = candles_today or candles_intraday or candles_hist

    test_telegram()
    test_full_pipeline(candles_to_use)

    print("\n" + "="*50)
    print("📝 DIAGNOSIS SUMMARY")
    print("="*50)
    print(f"  Token         : {'✅ Valid' if token_ok else '❌ Invalid'}")
    print(f"  Today's data  : {'✅ ' + str(len(candles_today)) + ' candles' if candles_today else '❌ No data'}")
    print(f"  Intraday API  : {'✅ ' + str(len(candles_intraday)) + ' candles' if candles_intraday else '❌ No data'}")
    print(f"  Historical    : {'✅ ' + str(len(candles_hist)) + ' candles (' + str(candles_hist_date) + ')' if candles_hist else '❌ No data'}")

    if not candles_today and not candles_intraday:
        print("""
  🔴 ROOT CAUSE: No intraday data available.
  
  Most likely reasons:
  1. ⏰ Market is CLOSED — NSE hours: 9:15 AM to 3:30 PM IST (Mon-Fri)
     Run this script during market hours to get live data.
  
  2. 📅 Upstox historical-candle API returns today's data ONLY during
     market hours or shortly after close. Outside those hours it returns empty.
  
  3. 🔑 Your ACCESS_TOKEN may be expired (tokens expire daily at ~3:30 AM).
     Regenerate at: https://upstox.com/developer/apps
  
  FIX FOR MAIN BOT:
  → Use the intraday API endpoint instead of historical-candle for today's data.
  → The fixed bot below handles this automatically.
        """)
else:
    print("\n  ❌ Cannot proceed — fix the token first.")

print("\n✅ Diagnostics complete.")