"""
📊 NSE WATCHLIST — REAL-TIME SIGNAL BOT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DELAY FIX — HOW IT WORKS:
  Old code scanned every 60s and checked bar[-2] always →
  signal came 3-7 minutes AFTER bar closed on TradingView.

  This version:
  • Polls every 15 seconds
  • Tracks the last bar[-1] TIMESTAMP per stock
  • When timestamp CHANGES → previous bar just CLOSED
  • At that exact moment checks for crossover → fires instantly
  • Max delay = 15s from bar close (same as TradingView bar-close alert)
  • No 10-min digest — only pure crossover signals
"""

import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta

# ══════════════════════════════════════════════════════
# 🔐  CONFIG — update ACCESS_TOKEN daily
# ══════════════════════════════════════════════════════

ACCESS_TOKEN        = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiIyQkNCNzQiLCJqdGkiOiI2OTlkMjQ5OTA0NTQxZTc2ZWRkMzMzODMiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6dHJ1ZSwiaWF0IjoxNzcxOTA2MjAxLCJpc3MiOiJ1ZGFwaS1nYXRld2F5LXNlcnZpY2UiLCJleHAiOjE3NzE5NzA0MDB9.k8M6pdpFGofqQUBiyDa0teyS3LqPq9afMSQ2pO0ZWss"
TELEGRAM_BOT_TOKEN = "8539235085:AAH64vStKl89iWFVhJ06rvp4arsC7of51Bk"
CHAT_IDS            = ["1336874504", "-1003655311849"]

# ── Indicator — must match TradingView exactly ──
ATR_PERIOD = 10
MULTIPLIER = 3.0

# ── Poll every 15s → alert within 15s of bar close ──
# Do NOT go below 10s (Upstox API rate limits)
POLL_INTERVAL = 15

HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Accept": "application/json"}

# ══════════════════════════════════════════════════════
# 📋  WATCHLIST
# ══════════════════════════════════════════════════════

WATCHLIST = [
    {"no":  1, "symbol": "PAGEIND",    "name": "Page Industries",        "instrument_key": "NSE_EQ|INE761H01022"},
    {"no":  2, "symbol": "SHREECEM",   "name": "Shree Cement",           "instrument_key": "NSE_EQ|INE070A01015"},
    {"no":  3, "symbol": "MARUTI",     "name": "Maruti Suzuki",          "instrument_key": "NSE_EQ|INE585B01010"},
    {"no":  4, "symbol": "SOLARINDS",  "name": "Solar Industries",       "instrument_key": "NSE_EQ|INE343H01029"},
    {"no":  5, "symbol": "PAYTM",      "name": "Paytm",                  "instrument_key": "NSE_EQ|INE982J01020"},
    {"no":  6, "symbol": "BOSCHLTD",   "name": "Bosch Ltd",              "instrument_key": "NSE_EQ|INE323A01026"},
    {"no":  7, "symbol": "DIXON",      "name": "Dixon Technologies",     "instrument_key": "NSE_EQ|INE935N01020"},
    {"no":  8, "symbol": "ULTRACEMCO", "name": "UltraTech Cement",       "instrument_key": "NSE_EQ|INE481G01011"},
    {"no":  9, "symbol": "JIOFIN",     "name": "Jio Financial Services", "instrument_key": "NSE_EQ|INE758T01015"},
    {"no": 10, "symbol": "OFSS",       "name": "Oracle Fin. Services",   "instrument_key": "NSE_EQ|INE881D01027"},
    {"no": 11, "symbol": "POLYCAB",    "name": "Polycab India",          "instrument_key": "NSE_EQ|INE455K01017"},
    {"no": 12, "symbol": "ABB",        "name": "ABB India",              "instrument_key": "NSE_EQ|INE117A01022"},
    {"no": 13, "symbol": "DIVISLAB",   "name": "Divi's Laboratories",    "instrument_key": "NSE_EQ|INE361B01024"},
]

# ══════════════════════════════════════════════════════
# ⏰  NSE MARKET HOURS  9:15 AM – 3:30 PM IST  Mon–Fri
# ══════════════════════════════════════════════════════

def is_nse_open():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    hm = (now.hour, now.minute)
    return (9, 15) <= hm < (15, 30)

def next_open_str():
    now = datetime.now()
    wd  = now.weekday()
    hm  = (now.hour, now.minute)
    if wd >= 5 or (wd == 4 and hm >= (15, 30)):
        days = 7 - wd
        d    = (datetime.now() + timedelta(days=days)).strftime("%d %b")
        return f"Monday {d} at 09:15 IST"
    if hm >= (15, 30):
        return "Tomorrow 09:15 IST"
    return "Soon"

# ══════════════════════════════════════════════════════
# ✅  TOKEN
# ══════════════════════════════════════════════════════

def validate_token():
    try:
        r = requests.get("https://api.upstox.com/v2/user/profile",
                         headers=HEADERS, timeout=10)
        if r.status_code == 200:
            u = r.json().get("data", {})
            print(f"✅ Token OK — {u.get('user_name')} ({u.get('email')})")
            return True
        print(f"❌ Token {r.status_code}: {r.text[:150]}")
        send_telegram(f"⚠️ <b>Token Invalid ({r.status_code})</b>\nRegenerate at upstox.com/developer/apps")
        return False
    except Exception as e:
        print(f"❌ Token error: {e}")
        return False

# ══════════════════════════════════════════════════════
# 📡  TELEGRAM
# ══════════════════════════════════════════════════════

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for cid in CHAT_IDS:
        try:
            r = requests.post(url, data={
                "chat_id": cid, "text": msg, "parse_mode": "HTML"
            }, timeout=10)
            if r.status_code != 200:
                print(f"  ⚠️ Telegram [{cid}]: {r.text[:80]}")
        except Exception as e:
            print(f"  ⚠️ Telegram error [{cid}]: {e}")

# ══════════════════════════════════════════════════════
# 📊  FETCH — intraday first (fastest live data)
# ══════════════════════════════════════════════════════

def fetch_candles(instrument_key, symbol):
    # Method 1: Intraday (real-time, fastest during market hours)
    url = f"https://api.upstox.com/v2/historical-candle/intraday/{instrument_key}/1minute"
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            c = r.json().get("data", {}).get("candles", [])
            if c:
                return c
        elif r.status_code == 401:
            print(f"  ❌ [{symbol}] Token expired!")
            send_telegram("⚠️ <b>Token Expired!</b>\nRegenerate at upstox.com/developer/apps")
            return []
    except Exception as e:
        print(f"  [{symbol}] Intraday error: {e}")

    # Method 2: Historical today fallback
    today = datetime.now().strftime("%Y-%m-%d")
    url   = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/1minute/{today}/{today}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            c = r.json().get("data", {}).get("candles", [])
            if c:
                return c
    except Exception as e:
        print(f"  [{symbol}] Historical today error: {e}")

    return []

def build_df(candles):
    cols = ["datetime","open","high","low","close","volume"]
    if candles and len(candles[0]) == 7:
        cols.append("oi")
    df = pd.DataFrame(candles, columns=cols)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)
    return df[["open","high","low","close","volume"]].astype(float)

# ══════════════════════════════════════════════════════
# 📈  INDICATOR — exact TradingView ta.supertrend()
#   direction = -1 → BULLISH (green, ST below price)
#   direction = +1 → BEARISH (red,   ST above price)
# ══════════════════════════════════════════════════════

def wilder_rma(series, period):
    alpha  = 1.0 / period
    vals   = series.values
    result = np.full(len(vals), np.nan)
    start  = next((i for i, v in enumerate(vals) if not np.isnan(v)), None)
    if start is None or start + period > len(vals):
        return pd.Series(result, index=series.index)
    result[start + period - 1] = np.nanmean(vals[start:start + period])
    for i in range(start + period, len(vals)):
        result[i] = alpha * vals[i] + (1.0 - alpha) * result[i - 1]
    return pd.Series(result, index=series.index)

def heiken_ashi(df):
    n  = len(df)
    hc = (df["open"] + df["high"] + df["low"] + df["close"]) / 4
    ho = np.zeros(n)
    ho[0] = (df["open"].iloc[0] + df["close"].iloc[0]) / 2.0
    for i in range(1, n):
        ho[i] = (ho[i-1] + hc.iloc[i-1]) / 2.0
    s = pd.Series(ho, index=df.index)
    return pd.DataFrame({
        "open":   s,
        "high":   pd.concat([df["high"], s, hc], axis=1).max(axis=1),
        "low":    pd.concat([df["low"],  s, hc], axis=1).min(axis=1),
        "close":  hc,
        "volume": df["volume"],
    }, index=df.index)

def calc_supertrend(ha, period, factor):
    pc  = ha["close"].shift(1)
    tr  = pd.concat([
        ha["high"] - ha["low"],
        (ha["high"] - pc).abs(),
        (ha["low"]  - pc).abs(),
    ], axis=1).max(axis=1)
    atr = wilder_rma(tr, period)
    src = (ha["high"] + ha["low"]) / 2.0
    ru  = (src + factor * atr).values
    rl  = (src - factor * atr).values
    cl  = ha["close"].values
    n   = len(ha)

    up = np.full(n, np.nan)
    lo = np.full(n, np.nan)
    di = np.full(n, np.nan)
    st = np.full(n, np.nan)

    for i in range(n):
        if np.isnan(ru[i]):
            continue
        if i == 0 or np.isnan(up[i-1]):
            up[i]=ru[i]; lo[i]=rl[i]; di[i]=1; st[i]=up[i]
            continue
        lo[i] = rl[i] if (rl[i] > lo[i-1] or cl[i-1] < lo[i-1]) else lo[i-1]
        up[i] = ru[i] if (ru[i] < up[i-1] or cl[i-1] > up[i-1]) else up[i-1]
        if di[i-1] == 1:
            di[i] = -1 if cl[i] > up[i-1] else 1
        else:
            di[i] =  1 if cl[i] < lo[i-1] else -1
        st[i] = lo[i] if di[i] == -1 else up[i]

    ha = ha.copy()
    ha["direction"]  = di
    ha["supertrend"] = st
    return ha

# ══════════════════════════════════════════════════════
# 📊  PER-STOCK STATE
# ══════════════════════════════════════════════════════

last_bar_time = {}   # symbol → pd.Timestamp of bar[-1] from last scan
last_signal   = {}   # symbol → "BUY 🟢" / "SELL 🔴" / None

# ══════════════════════════════════════════════════════
# 🔔  ALERT
# ══════════════════════════════════════════════════════

def fire_alert(stock, signal, ha_close, st_val, bar_time):
    sym  = stock["symbol"]
    name = stock["name"]

    if "BUY" in signal:
        action    = "📈 Go LONG  |  Buy CE / Buy Stock"
        trend_now = "Trend flipped → <b>BULLISH</b> 🟢"
    else:
        action    = "📉 Go SHORT |  Buy PE / Sell Stock"
        trend_now = "Trend flipped → <b>BEARISH</b> 🔴"

    send_telegram(
        f"🔔 <b>NEW SIGNAL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Stock      : <b>{sym}</b>  ({name})\n"
        f"🚀 Signal     : <b>{signal}</b>\n"
        f"💡 Action     : {action}\n"
        f"📌 {trend_now}\n"
        f"⚙️ Indicator  : Supertrend({ATR_PERIOD},{MULTIPLIER}) | 3-Min HA\n"
        f"💰 HA Close   : <b>{ha_close}</b>\n"
        f"📉 Supertrend : {st_val}\n"
        f"📊 Bar Closed : {bar_time.strftime('%H:%M')}\n"
        f"🕒 Alert Time : {datetime.now().strftime('%H:%M:%S IST')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    print(f"\n  🔔 SIGNAL → {sym}: {signal} | "
          f"bar={bar_time.strftime('%H:%M')} "
          f"alert={datetime.now().strftime('%H:%M:%S')}\n")

# ══════════════════════════════════════════════════════
# 🔁  PROCESS ONE STOCK — bar-close detection
#
# KEY LOGIC:
#   Every 15s we fetch fresh 1-min candles and resample to 3-min.
#   bar[-1] = FORMING bar (its timestamp = current 3-min slot)
#   bar[-2] = last CLOSED bar
#
#   We store bar[-1].timestamp from the previous scan.
#   If it CHANGED → the old forming bar just became a closed bar.
#   That is the exact moment TradingView fires a bar-close alert.
#   We check bar[-2] vs bar[-3] for direction crossover and fire.
# ══════════════════════════════════════════════════════

def process_stock(stock):
    sym = stock["symbol"]
    try:
        raw = fetch_candles(stock["instrument_key"], sym)
        if not raw:
            print(f"  [{sym}] ⚠️  No data")
            return

        df = build_df(raw)
        df = df[~df.index.duplicated(keep="last")]
        df.sort_index(inplace=True)

        df3 = df.resample("3T").agg({
            "open":"first","high":"max",
            "low":"min","close":"last","volume":"sum"
        }).dropna()

        if len(df3) < ATR_PERIOD + 10:
            print(f"  [{sym}] ⚠️  Only {len(df3)} 3-min bars")
            return

        ha = heiken_ashi(df3)
        ha = calc_supertrend(ha, ATR_PERIOD, MULTIPLIER)

        if len(ha) < 4:
            return

        current_bar_time = ha.index[-1]   # timestamp of forming bar
        prev_bar_time    = last_bar_time.get(sym)

        # First scan — record timestamp, don't check signal yet
        if prev_bar_time is None:
            last_bar_time[sym] = current_bar_time
            d = ha["direction"].iloc[-2]
            print(f"  [{sym}] INIT bar={current_bar_time.strftime('%H:%M')} "
                  f"dir={'BULL' if d==-1 else 'BEAR'}")
            return

        # Bar still forming — skip
        if current_bar_time == prev_bar_time:
            d = ha["direction"].iloc[-2]
            print(f"  [{sym}] wait {current_bar_time.strftime('%H:%M')} "
                  f"closed={'BULL' if d==-1 else 'BEAR'}")
            return

        # ✅ New bar started → previous bar just CLOSED
        just_closed_time   = prev_bar_time
        last_bar_time[sym] = current_bar_time

        # bar[-2] = the bar that JUST closed (confirmed)
        # bar[-3] = the bar before it (also confirmed)
        prev_dir = ha["direction"].iloc[-3]
        curr_dir = ha["direction"].iloc[-2]
        ha_close = round(float(ha["close"].iloc[-2]), 2)
        st_val   = round(float(ha["supertrend"].iloc[-2]), 2)

        print(f"  [{sym}] ✅ CLOSED {just_closed_time.strftime('%H:%M')} "
              f"prev={'BULL' if prev_dir==-1 else 'BEAR'} "
              f"curr={'BULL' if curr_dir==-1 else 'BEAR'} "
              f"HA={ha_close} ST={st_val}")

        if np.isnan(prev_dir) or np.isnan(curr_dir):
            return

        # Crossover check
        signal = None
        if curr_dir == -1 and prev_dir == 1:    signal = "BUY 🟢"
        elif curr_dir == 1 and prev_dir == -1:  signal = "SELL 🔴"

        if signal and signal != last_signal.get(sym):
            fire_alert(stock, signal, ha_close, st_val, just_closed_time)
            last_signal[sym] = signal

    except Exception as e:
        import traceback
        print(f"  [{sym}] ❌ {e}")
        traceback.print_exc()

# ══════════════════════════════════════════════════════
# 🚀  STARTUP
# ══════════════════════════════════════════════════════

print("=" * 58)
print("  📊  NSE WATCHLIST — REAL-TIME SIGNAL BOT")
print(f"  ⚙️   Supertrend({ATR_PERIOD},{MULTIPLIER}) | 3-Min Heiken Ashi")
print(f"  ⚡  Poll: {POLL_INTERVAL}s | Alert within {POLL_INTERVAL}s of bar close")
print(f"  ⏰  NSE hours: 09:15 – 15:30 IST  Mon–Fri")
print("=" * 58)

if not validate_token():
    exit(1)

send_telegram(
    f"🤖 <b>NSE Watchlist Real-Time Bot STARTED</b>\n"
    f"📊 Stocks    : {len(WATCHLIST)} stocks\n"
    f"⚙️ Indicator : Supertrend({ATR_PERIOD},{MULTIPLIER}) | 3-Min HA\n"
    f"⚡ Speed     : Alert within {POLL_INTERVAL}s of bar close\n"
    f"🔔 Alerts    : Crossover only — no digest, no spam\n"
    f"⏰ Hours     : Mon–Fri  09:15 – 15:30 IST\n"
    f"🕒 Started   : {datetime.now().strftime('%d %b %Y  %H:%M:%S IST')}\n\n"
    f"📋 <b>Watchlist ({len(WATCHLIST)} stocks):</b>\n" +
    "\n".join(f"  {s['no']:>2}. {s['symbol']:<12} {s['name']}" for s in WATCHLIST)
)

print(f"\n✅ Bot running — polling every {POLL_INTERVAL}s\n")

market_closed_notified = False

# ══════════════════════════════════════════════════════
# 🔄  MAIN LOOP
# ══════════════════════════════════════════════════════

while True:
    try:
        now = datetime.now()

        # ── Market closed ──────────────────────────────
        if not is_nse_open():
            if not market_closed_notified:
                send_telegram(
                    f"💤 <b>NSE Market CLOSED</b>\n"
                    f"🕒 {now.strftime('%d %b %Y  %H:%M:%S IST')}\n"
                    f"⏰ Next open: {next_open_str()}\n"
                    f"Bot sleeping — resumes at 09:15 IST."
                )
                print(f"\n💤 NSE closed @ {now.strftime('%H:%M:%S')} — sleeping...")
                market_closed_notified = True
            time.sleep(30)
            continue

        # ── Market just opened ─────────────────────────
        if market_closed_notified:
            market_closed_notified = False
            last_bar_time.clear()
            last_signal.clear()
            send_telegram(
                f"🟢 <b>NSE Market OPENED</b>\n"
                f"🕒 {now.strftime('%d %b %Y  %H:%M:%S IST')}\n"
                f"🔍 Live scanning {len(WATCHLIST)} stocks every {POLL_INTERVAL}s..."
            )
            print(f"\n🟢 NSE opened — scanning started")

        # ── Poll all stocks ────────────────────────────
        t0 = datetime.now()
        print(f"\n⏱ Poll @ {t0.strftime('%H:%M:%S IST')}")

        for stock in WATCHLIST:
            process_stock(stock)

        elapsed = (datetime.now() - t0).total_seconds()
        sleep   = max(1, POLL_INTERVAL - elapsed)
        print(f"  done in {elapsed:.1f}s — next poll in {sleep:.0f}s")
        time.sleep(sleep)

    except KeyboardInterrupt:
        print("\n🛑 Bot stopped.")
        send_telegram("🛑 <b>NSE Watchlist Bot stopped.</b>")
        break
    except Exception as e:
        import traceback
        print(f"❌ Loop error: {e}")
        traceback.print_exc()
        time.sleep(POLL_INTERVAL)