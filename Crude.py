"""
🛢️ MCX CRUDE OIL LIVE SIGNAL BOT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Auto-fetches current near-month Crude Oil contract from Upstox MCX JSON
• Scans every 60 seconds during MCX market hours
• MCX hours: Mon–Fri 09:00–23:30 IST | Sat 09:00–14:00 IST
• Indicator: Supertrend(10, 3.0) on 3-Min Heiken Ashi
• Direction matches TradingView exactly:
    -1 = BULLISH (green), +1 = BEARISH (red)
• Signal fires on last CLOSED bar only (zero repainting)
• Real-time Telegram alert on crossover
• 10-min digest with current trend status
• Daily instrument key auto-refresh at 06:05 AM
"""

import requests
import gzip
import json
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta

# ══════════════════════════════════════════════════════
# 🔐 CONFIG  — update ACCESS_TOKEN daily
# ══════════════════════════════════════════════════════

ACCESS_TOKEN        = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiIyQkNCNzQiLCJqdGkiOiI2OTliZGE5MTdmODBmOTFjMDgxNWM2YjgiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6dHJ1ZSwiaWF0IjoxNzcxODIxNzEzLCJpc3MiOiJ1ZGFwaS1nYXRld2F5LXNlcnZpY2UiLCJleHAiOjE3NzE4ODQwMDB9.XeGw4z7s9Hyqlsry3beozoqiLyUNP3l9ssqacyElKio"
TELEGRAM_BOT_TOKEN = "8539235085:AAH64vStKl89iWFVhJ06rvp4arsC7of51Bk"
CHAT_IDS            = ["1336874504", "-1003655311849"]

# ── Indicator — must match TradingView exactly ──
ATR_PERIOD  = 10
MULTIPLIER  = 3.0

# ── Timing ──
SCAN_INTERVAL_SEC   = 60    # scan every 60 s
STATUS_INTERVAL_MIN = 10    # digest every 10 min

# ══════════════════════════════════════════════════════
# ⏰  MCX MARKET HOURS (IST)
#   Mon–Fri : 09:00 – 23:30
#   Saturday: 09:00 – 14:00
#   Sunday  : Closed
# ══════════════════════════════════════════════════════

def is_mcx_open():
    now = datetime.now()
    wd  = now.weekday()          # 0=Mon … 6=Sun
    hm  = (now.hour, now.minute)
    if wd == 6:                  return False
    if wd == 5:                  return (9, 0) <= hm < (14, 0)
    return (9, 0) <= hm < (23, 30)

def next_open_str():
    now = datetime.now()
    wd  = now.weekday()
    hm  = (now.hour, now.minute)
    if wd == 6:                            return "Monday 09:00 IST"
    if wd == 5 and hm >= (14, 0):          return "Monday 09:00 IST"
    if wd  < 5 and hm >= (23, 30):
        return "Monday 09:00 IST" if wd == 4 else "Tomorrow 09:00 IST"
    return "Soon"

# ══════════════════════════════════════════════════════
# 🔎  AUTO-RESOLVE MCX CRUDE OIL INSTRUMENT KEY
#     Downloads official Upstox MCX JSON every day
#     Picks nearest-expiry CRUDEOIL FUT automatically
# ══════════════════════════════════════════════════════

MCX_JSON_URL = "https://assets.upstox.com/market-quote/instruments/exchange/MCX.json.gz"

def fetch_mcx_instruments():
    print("📥 Downloading MCX instrument list from Upstox...")
    try:
        r = requests.get(MCX_JSON_URL, timeout=30)
        r.raise_for_status()
        data = json.loads(gzip.decompress(r.content).decode("utf-8"))
        print(f"  ✅ {len(data)} MCX instruments loaded")
        return data
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return []

def find_near_month(instruments, underlying="CRUDEOIL"):
    today      = datetime.now()
    candidates = []
    for inst in instruments:
        if inst.get("instrument_type") != "FUT":
            continue
        if inst.get("underlying_symbol", "").upper() != underlying.upper():
            continue
        exp_ms = inst.get("expiry")
        if exp_ms is None:
            continue
        exp_dt = datetime.fromtimestamp(exp_ms / 1000)
        if exp_dt.date() < today.date():
            continue
        candidates.append({
            "instrument_key": inst["instrument_key"],
            "trading_symbol": inst.get("trading_symbol", ""),
            "expiry_dt":      exp_dt,
        })
    if not candidates:
        return None, None, None
    candidates.sort(key=lambda x: x["expiry_dt"])
    b = candidates[0]
    return b["instrument_key"], b["trading_symbol"], b["expiry_dt"]

# ══════════════════════════════════════════════════════
# Internal state
# ══════════════════════════════════════════════════════

last_signal     = None    # "BUY 🟢" / "SELL 🔴" / None
last_alert_time = None    # datetime
crude_state     = {}      # current state dict for digest
HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Accept": "application/json"}

# ══════════════════════════════════════════════════════
# ✅  TOKEN VALIDATION
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
        send_telegram(
            f"⚠️ <b>Token Invalid ({r.status_code})</b>\n"
            f"Regenerate at upstox.com/developer/apps\nBot stopped."
        )
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
# 📊  DATA FETCH
# ══════════════════════════════════════════════════════

def fetch_candles(instrument_key, symbol):
    # Method 1: Intraday API (live candles during market hours)
    url = f"https://api.upstox.com/v2/historical-candle/intraday/{instrument_key}/1minute"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            c = r.json().get("data", {}).get("candles", [])
            if c:
                print(f"  [{symbol}] Intraday → {len(c)} candles ✅")
                return c
        elif r.status_code == 401:
            print(f"  ❌ Token expired!")
            send_telegram("⚠️ <b>Token Expired!</b>\nRegenerate at upstox.com/developer/apps")
            return []
        else:
            print(f"  [{symbol}] Intraday {r.status_code}: {r.text[:80]}")
    except Exception as e:
        print(f"  [{symbol}] Intraday error: {e}")

    # Method 2: Historical today
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/1minute/{today}/{today}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            c = r.json().get("data", {}).get("candles", [])
            if c:
                print(f"  [{symbol}] Historical today → {len(c)} candles ✅")
                return c
    except Exception as e:
        print(f"  [{symbol}] Historical today error: {e}")

    print(f"  [{symbol}] ❌ No data from any source")
    return []

def build_df(candles):
    """Handles both 6-col and 7-col (with OI) Upstox responses."""
    cols = ["datetime", "open", "high", "low", "close", "volume"]
    if candles and len(candles[0]) == 7:
        cols.append("oi")
    df = pd.DataFrame(candles, columns=cols)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)
    return df[["open", "high", "low", "close", "volume"]].astype(float)

# ══════════════════════════════════════════════════════
# 📈  INDICATOR — exact TradingView ta.supertrend()
#
#   direction = -1 → BULLISH (green, ST line below price)
#   direction = +1 → BEARISH (red,   ST line above price)
#   BUY  signal : prev +1 → curr -1
#   SELL signal : prev -1 → curr +1
# ══════════════════════════════════════════════════════

def wilder_rma(series, period):
    """Wilder's smoothing — matches ta.rma() in Pine Script v5."""
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
            up[i] = ru[i]; lo[i] = rl[i]; di[i] = 1; st[i] = up[i]
            continue
        # Pine Script exact band-locking
        lo[i] = rl[i] if (rl[i] > lo[i-1] or cl[i-1] < lo[i-1]) else lo[i-1]
        up[i] = ru[i] if (ru[i] < up[i-1] or cl[i-1] > up[i-1]) else up[i-1]
        # Direction flip
        if di[i-1] == 1:
            di[i] = -1 if cl[i] > up[i-1] else 1
        else:
            di[i] =  1 if cl[i] < lo[i-1] else -1
        st[i] = lo[i] if di[i] == -1 else up[i]

    ha = ha.copy()
    ha["direction"]  = di   # -1=BULL, +1=BEAR
    ha["supertrend"] = st
    return ha

# ══════════════════════════════════════════════════════
# 🚨  SIGNAL DETECTION
#   Uses bar[-2] (last fully closed) NOT bar[-1] (forming)
#   Compares bar[-3] → bar[-2] crossover — zero repainting
# ══════════════════════════════════════════════════════

def detect_signal(ha):
    if len(ha) < 3:
        return None
    prev = ha["direction"].iloc[-3]
    curr = ha["direction"].iloc[-2]
    if np.isnan(prev) or np.isnan(curr):
        return None
    if curr == -1 and prev == 1:   return "BUY 🟢"
    if curr ==  1 and prev == -1:  return "SELL 🔴"
    return None

# ══════════════════════════════════════════════════════
# 🔔  ALERT
# ══════════════════════════════════════════════════════

def send_signal_alert(trading_symbol, expiry, signal, ha_close, st_val):
    global last_signal, last_alert_time

    if "BUY" in signal:
        action    = "📈 Go LONG  |  Buy CE / Buy Futures"
        trend_now = "Trend flipped → <b>BULLISH</b> 🟢"
    else:
        action    = "📉 Go SHORT |  Buy PE / Sell Futures"
        trend_now = "Trend flipped → <b>BEARISH</b> 🔴"

    send_telegram(
        f"🔔 <b>NEW SIGNAL — CRUDE OIL MCX</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛢️  Contract   : <b>{trading_symbol}</b>\n"
        f"📅 Expiry     : {expiry.strftime('%d %b %Y')}\n"
        f"🚀 Signal     : <b>{signal}</b>\n"
        f"💡 Action     : {action}\n"
        f"📌 {trend_now}\n"
        f"⏰ Timeframe  : 3-Min Heiken Ashi\n"
        f"⚙️ Indicator  : Supertrend({ATR_PERIOD}, {MULTIPLIER})\n"
        f"💰 HA Close   : <b>{ha_close}</b>\n"
        f"📉 Supertrend : {st_val}\n"
        f"🕒 Time       : {datetime.now().strftime('%H:%M:%S IST')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    last_signal     = signal
    last_alert_time = datetime.now()
    print(f"  🔔 SIGNAL → CRUDEOIL: {signal} @ {datetime.now().strftime('%H:%M:%S')}")

# ══════════════════════════════════════════════════════
# 🔁  PROCESS CRUDE OIL
# ══════════════════════════════════════════════════════

def process_crude(instrument_key, trading_symbol, expiry):
    global crude_state
    sym = "CRUDEOIL"
    try:
        # 1. Fetch live candles
        raw = fetch_candles(instrument_key, sym)
        if not raw:
            crude_state = {"error": "No data — API issue or market just opened"}
            return

        # 2. Build DataFrame
        df = build_df(raw)
        df = df[~df.index.duplicated(keep="last")]
        df.sort_index(inplace=True)

        # 3. Resample → 3-min
        df3 = df.resample("3T").agg({
            "open":"first", "high":"max",
            "low":"min",    "close":"last", "volume":"sum"
        }).dropna()

        min_bars = ATR_PERIOD + 10
        if len(df3) < min_bars:
            crude_state = {"error": f"Only {len(df3)} bars (need {min_bars}, wait a few min)"}
            print(f"  [CRUDEOIL] ⚠️ Only {len(df3)} 3-min bars — waiting...")
            return

        # 4. Heiken Ashi
        ha = heiken_ashi(df3)

        # 5. Supertrend
        ha = calc_supertrend(ha, ATR_PERIOD, MULTIPLIER)

        # 6. Current state — bar[-2] (last fully closed, not forming bar[-1])
        last_closed   = ha.iloc[-2]
        curr_dir      = int(last_closed["direction"])
        ha_close      = round(float(last_closed["close"]), 2)
        st_val        = round(float(last_closed["supertrend"]), 2)
        trend_str     = "BULLISH 📈" if curr_dir == -1 else "BEARISH 📉"
        bar_time      = ha.index[-2].strftime("%H:%M")

        # Console debug
        forming       = ha.iloc[-1]
        forming_dir   = int(forming["direction"]) if not np.isnan(forming["direction"]) else "?"
        print(f"  [CRUDEOIL] closed={bar_time} dir={'BULL' if curr_dir==-1 else 'BEAR'} "
              f"HA={ha_close} ST={st_val} | forming_dir={'BULL' if forming_dir==-1 else 'BEAR'}")

        # 7. Signal — bar[-3]→bar[-2] crossover (both closed)
        signal = detect_signal(ha)

        if signal and signal != last_signal:
            send_signal_alert(trading_symbol, expiry, signal, ha_close, st_val)

        # 8. Update state for digest
        crude_state = {
            "trading_symbol": trading_symbol,
            "expiry":         expiry,
            "direction":      curr_dir,
            "trend":          trend_str,
            "ha_close":       ha_close,
            "supertrend":     st_val,
            "bar_time":       bar_time,
            "last_signal":    last_signal or "—",
            "sig_time":       last_alert_time.strftime("%H:%M:%S")
                              if last_alert_time else "—",
            "bars":           len(ha),
            "error":          None,
        }

    except Exception as e:
        import traceback
        print(f"  [CRUDEOIL] ❌ {e}")
        traceback.print_exc()
        crude_state = {"error": str(e)[:100]}

# ══════════════════════════════════════════════════════
# 📋  10-MIN STATUS DIGEST
# ══════════════════════════════════════════════════════

def send_digest():
    now = datetime.now().strftime("%d %b %Y  %H:%M:%S")
    mkt = "🟢 OPEN" if is_mcx_open() else f"🔴 CLOSED (opens {next_open_str()})"

    if crude_state.get("error"):
        send_telegram(
            f"📋 <b>CRUDE OIL STATUS — 10 MIN</b>\n"
            f"🕒 {now} IST\n"
            f"🏪 MCX : {mkt}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"❌ Error: {crude_state['error']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏭ Next digest in {STATUS_INTERVAL_MIN} min"
        )
    else:
        d    = crude_state.get("direction", 1)
        icon = "🟢" if d == -1 else "🔴"
        exp_str = crude_state["expiry"].strftime("%d %b %Y") if crude_state.get("expiry") else "—"

        send_telegram(
            f"📋 <b>CRUDE OIL STATUS — 10 MIN</b>\n"
            f"🕒 {now} IST\n"
            f"🏪 MCX : {mkt}\n"
            f"⚙️ Supertrend({ATR_PERIOD},{MULTIPLIER}) | 3-Min HA\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛢️  Contract   : <b>{crude_state.get('trading_symbol','—')}</b>\n"
            f"📅 Expiry     : {exp_str}\n"
            f"{icon} Trend       : <b>{crude_state.get('trend','—')}</b>\n"
            f"💰 HA Close   : {crude_state.get('ha_close','—')}\n"
            f"📉 Supertrend : {crude_state.get('supertrend','—')}\n"
            f"🕒 Bar Time   : {crude_state.get('bar_time','—')}\n"
            f"📌 Last Signal: {crude_state.get('last_signal','—')}  @ {crude_state.get('sig_time','—')}\n"
            f"📊 Bars loaded: {crude_state.get('bars','—')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏭ Next digest in {STATUS_INTERVAL_MIN} min"
        )
    print(f"  📋 Digest sent @ {datetime.now().strftime('%H:%M:%S')}")

# ══════════════════════════════════════════════════════
# 🚀  STARTUP
# ══════════════════════════════════════════════════════

print("=" * 58)
print("  🛢️   MCX CRUDE OIL LIVE SIGNAL BOT")
print(f"  ⚙️   Supertrend({ATR_PERIOD},{MULTIPLIER}) | 3-Min Heiken Ashi")
print(f"  ⏰  MCX hours: 09:00–23:30 IST  Mon–Fri | Sat 09:00–14:00")
print("=" * 58)

if not validate_token():
    print("🛑 Fix your Upstox token first. Exiting.")
    exit(1)

# Resolve instrument key
print("\n🔎 Resolving MCX Crude Oil instrument key...")
mcx_instruments = fetch_mcx_instruments()
instrument_key, trading_symbol, expiry = find_near_month(mcx_instruments, "CRUDEOIL")

if not instrument_key:
    msg = "❌ Could not find active CRUDEOIL FUT contract in MCX instruments.\nExiting."
    print(msg)
    send_telegram(f"⚠️ <b>Bot Error</b>\n{msg}")
    exit(1)

print(f"  ✅ Contract : {trading_symbol}")
print(f"  ✅ Key      : {instrument_key}")
print(f"  ✅ Expiry   : {expiry.strftime('%d %b %Y')}")

send_telegram(
    f"🤖 <b>MCX Crude Oil Bot STARTED</b>\n"
    f"🛢️  Contract  : <b>{trading_symbol}</b>\n"
    f"📅 Expiry    : {expiry.strftime('%d %b %Y')}\n"
    f"⚙️ Indicator : Supertrend({ATR_PERIOD},{MULTIPLIER}) | 3-Min HA\n"
    f"🔔 Alerts    : Instant on crossover (no repeat spam)\n"
    f"📋 Digest    : Every {STATUS_INTERVAL_MIN} min\n"
    f"⏰ MCX Hours : Mon–Fri 09:00–23:30 | Sat 09:00–14:00\n"
    f"🕒 Started   : {datetime.now().strftime('%d %b %Y  %H:%M:%S IST')}"
)

print(f"\n✅ Bot running. Scanning every {SCAN_INTERVAL_SEC}s during MCX hours.\n")

last_digest_time       = datetime.now() - timedelta(minutes=STATUS_INTERVAL_MIN)
market_closed_notified = False
instrument_refresh_day = datetime.now().date()

# ══════════════════════════════════════════════════════
# 🔄  MAIN LOOP — 24/7, active during MCX market hours
# ══════════════════════════════════════════════════════

while True:
    try:
        now = datetime.now()

        # ── Daily instrument key refresh at 06:05 AM ──────
        if now.date() != instrument_refresh_day and now.hour == 6 and now.minute >= 5:
            print("\n🔄 Daily instrument key refresh...")
            new_instr = fetch_mcx_instruments()
            new_key, new_ts, new_exp = find_near_month(new_instr, "CRUDEOIL")
            if new_key:
                instrument_key    = new_key
                trading_symbol    = new_ts
                expiry            = new_exp
                instrument_refresh_day = now.date()
                # Reset signals for new contract day
                last_signal       = None
                last_alert_time   = None
                crude_state       = {}
                print(f"  ✅ New contract: {trading_symbol}  exp {expiry.strftime('%d %b %Y')}")
                send_telegram(
                    f"🔄 <b>Contract Refreshed</b>\n"
                    f"🛢️ New contract : <b>{trading_symbol}</b>\n"
                    f"📅 Expiry       : {expiry.strftime('%d %b %Y')}\n"
                    f"🕒 {now.strftime('%d %b %Y  %H:%M IST')}"
                )
            else:
                print("  ⚠️ Could not refresh — keeping existing contract")

        # ── MCX closed ─────────────────────────────────────
        if not is_mcx_open():
            if not market_closed_notified:
                send_telegram(
                    f"💤 <b>MCX Market CLOSED</b>\n"
                    f"🕒 {now.strftime('%d %b %Y  %H:%M:%S IST')}\n"
                    f"⏰ Next open: {next_open_str()}\n"
                    f"Bot sleeping — resumes automatically."
                )
                print(f"\n💤 MCX closed @ {now.strftime('%H:%M:%S')} — sleeping...")
                market_closed_notified = True
            time.sleep(60)
            continue

        # ── MCX just opened ────────────────────────────────
        if market_closed_notified:
            market_closed_notified = False
            # Reset signals so each session starts fresh
            last_signal     = None
            last_alert_time = None
            crude_state     = {}
            send_telegram(
                f"🟢 <b>MCX Market OPENED</b>\n"
                f"🕒 {now.strftime('%d %b %Y  %H:%M:%S IST')}\n"
                f"🛢️ Contract : {trading_symbol}  (exp {expiry.strftime('%d %b %Y')})\n"
                f"🔍 Starting live Crude Oil scan..."
            )
            print(f"\n🟢 MCX opened — starting live scan")

        # ── Normal scan ────────────────────────────────────
        t0 = datetime.now()
        print(f"\n⏱ Scan @ {t0.strftime('%H:%M:%S IST')}")

        process_crude(instrument_key, trading_symbol, expiry)

        # 10-min digest
        if (datetime.now() - last_digest_time).total_seconds() >= STATUS_INTERVAL_MIN * 60:
            send_digest()
            last_digest_time = datetime.now()

        elapsed = (datetime.now() - t0).total_seconds()
        sleep   = max(0, SCAN_INTERVAL_SEC - elapsed)
        print(f"  ✅ Done in {elapsed:.1f}s — next scan in {sleep:.0f}s")
        time.sleep(sleep)

    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
        send_telegram("🛑 <b>MCX Crude Oil Bot manually stopped.</b>")
        break
    except Exception as e:
        import traceback
        print(f"❌ Loop error: {e}")
        traceback.print_exc()
        time.sleep(SCAN_INTERVAL_SEC)