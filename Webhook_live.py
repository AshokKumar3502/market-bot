"""
📊 NSE WATCHLIST — CLEAN SIGNAL BOT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Signal types:
  📶 Normal Signal    — Supertrend crossover only
  📶📶 Strong Signal    — Supertrend + Gap clear + Volume spike + VWAP side
  📶📶📶 Very Strong Signal — All above + RSI zone ok + 15-Min trend agrees

Telegram alert format (clean, nothing extra):
  PAGEIND
  Very Strong Signal
  BUY
  10:21

INSTALL:  pip install upstox-python-sdk pandas numpy requests
RUN:      python nse_signal_bot.py
"""

import upstox_client
import requests
import pandas as pd
import numpy as np
import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict

# ══════════════════════════════════════════════════════
# 🔐  CONFIG
# ══════════════════════════════════════════════════════

ACCESS_TOKEN       = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiIyQkNCNzQiLCJqdGkiOiI2OTlkMjQ5OTA0NTQxZTc2ZWRkMzMzODMiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6dHJ1ZSwiaWF0IjoxNzcxOTA2MjAxLCJpc3MiOiJ1ZGFwaS1nYXRld2F5LXNlcnZpY2UiLCJleHAiOjE3NzE5NzA0MDB9.k8M6pdpFGofqQUBiyDa0teyS3LqPq9afMSQ2pO0ZWss"
TELEGRAM_BOT_TOKEN = "8539235085:AAH64vStKl89iWFVhJ06rvp4arsC7of51Bk"
CHAT_IDS           = ["1336874504", "-1003655311849"]

ATR_PERIOD        = 10
MULTIPLIER        = 3.0
VOLUME_MULT       = 1.5    # volume must be ≥ this × 20-bar avg
RSI_PERIOD        = 14
RSI_OB            = 70     # overbought
RSI_OS            = 30     # oversold
GAP_END           = (9, 30)  # signals blocked before 9:30

REST_H = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Accept": "application/json"}

# ══════════════════════════════════════════════════════
# 📋  WATCHLIST
# ══════════════════════════════════════════════════════

WATCHLIST = [
    {"symbol": "PAGEIND",    "name": "Page Industries",        "key": "NSE_EQ|INE761H01022"},
    {"symbol": "SHREECEM",   "name": "Shree Cement",           "key": "NSE_EQ|INE070A01015"},
    {"symbol": "MARUTI",     "name": "Maruti Suzuki",          "key": "NSE_EQ|INE585B01010"},
    {"symbol": "SOLARINDS",  "name": "Solar Industries",       "key": "NSE_EQ|INE343H01029"},
    {"symbol": "PAYTM",      "name": "Paytm",                  "key": "NSE_EQ|INE982J01020"},
    {"symbol": "BOSCHLTD",   "name": "Bosch Ltd",              "key": "NSE_EQ|INE323A01026"},
    {"symbol": "DIXON",      "name": "Dixon Technologies",     "key": "NSE_EQ|INE935N01020"},
    {"symbol": "ULTRACEMCO", "name": "UltraTech Cement",       "key": "NSE_EQ|INE481G01011"},
    {"symbol": "JIOFIN",     "name": "Jio Financial Services", "key": "NSE_EQ|INE758T01015"},
    {"symbol": "OFSS",       "name": "Oracle Fin. Services",   "key": "NSE_EQ|INE881D01027"},
    {"symbol": "POLYCAB",    "name": "Polycab India",          "key": "NSE_EQ|INE455K01017"},
    {"symbol": "ABB",        "name": "ABB India",              "key": "NSE_EQ|INE117A01022"},
    {"symbol": "DIVISLAB",   "name": "Divi's Laboratories",    "key": "NSE_EQ|INE361B01024"},
]

KEY_TO_STOCK = {s["key"]: s for s in WATCHLIST}
ALL_KEYS     = [s["key"] for s in WATCHLIST]

# ══════════════════════════════════════════════════════
# ⏰  MARKET HOURS
# ══════════════════════════════════════════════════════

def is_nse_open():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    hm = (now.hour, now.minute)
    return (9, 15) <= hm < (15, 30)

def in_gap_window():
    hm = (datetime.now().hour, datetime.now().minute)
    return (9, 15) <= hm < GAP_END

def next_open_str():
    now = datetime.now()
    wd  = now.weekday()
    hm  = (now.hour, now.minute)
    if wd >= 5 or (wd == 4 and hm >= (15, 30)):
        d = (now + timedelta(days=7 - wd)).strftime("%d %b")
        return f"Monday {d} 09:15 IST"
    return "Tomorrow 09:15 IST" if hm >= (15, 30) else "Soon"

# ══════════════════════════════════════════════════════
# 📡  TELEGRAM — clean single-message sender
# ══════════════════════════════════════════════════════

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for cid in CHAT_IDS:
        try:
            requests.post(url, data={"chat_id": cid, "text": msg,
                                     "parse_mode": "HTML"}, timeout=10)
        except Exception as e:
            print(f"  ⚠️ Telegram: {e}")

def send_signal_alert(symbol, signal_type, direction, bar_ts):
    """
    Minimal alert — exactly 4 lines:
      Stock name
      Signal type
      BUY / SELL
      Timestamp
    """
    if "BUY" in direction:
        dir_line  = "🟢 BUY"
    else:
        dir_line  = "🔴 SELL"

    if signal_type == "normal":
        type_line = "📶 Normal Signal"
    elif signal_type == "strong":
        type_line = "📶📶 Strong Signal"
    else:
        type_line = "📶📶📶 Very Strong Signal"

    send_telegram(
        f"<b>{symbol}</b>\n"
        f"{type_line}\n"
        f"{dir_line}\n"
        f"🕒 {bar_ts.strftime('%H:%M  %d %b %Y')}"
    )

# ══════════════════════════════════════════════════════
# 📈  INDICATORS
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
    hc = (df["open"] + df["high"] + df["low"] + df["close"]) / 4.0
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
    up = np.full(n, np.nan); lo = np.full(n, np.nan)
    di = np.full(n, np.nan); st = np.full(n, np.nan)
    for i in range(n):
        if np.isnan(ru[i]): continue
        if i == 0 or np.isnan(up[i-1]):
            up[i]=ru[i]; lo[i]=rl[i]; di[i]=1; st[i]=up[i]; continue
        lo[i] = rl[i] if (rl[i] > lo[i-1] or cl[i-1] < lo[i-1]) else lo[i-1]
        up[i] = ru[i] if (ru[i] < up[i-1] or cl[i-1] > up[i-1]) else up[i-1]
        di[i] = (-1 if cl[i] > up[i-1] else 1) if di[i-1]==1 else (1 if cl[i] < lo[i-1] else -1)
        st[i] = lo[i] if di[i] == -1 else up[i]
    ha = ha.copy()
    ha["direction"]  = di
    ha["supertrend"] = st
    return ha

def calc_vwap(df1):
    session_start = df1.index[0].replace(hour=9, minute=15, second=0, microsecond=0)
    s = df1[df1.index >= session_start].copy()
    if s.empty: return np.nan
    tp = (s["high"] + s["low"] + s["close"]) / 3.0
    return float((tp * s["volume"]).cumsum().iloc[-1] / s["volume"].cumsum().iloc[-1])

def calc_rsi(close_series, period=14):
    delta = close_series.diff()
    ag = wilder_rma(delta.clip(lower=0), period)
    al = wilder_rma((-delta).clip(lower=0), period)
    rs = ag / al.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return float(rsi.iloc[-1]) if not rsi.empty else np.nan

def get_15min_dir(df1):
    df15 = df1.resample("15T").agg({
        "open":"first","high":"max","low":"min","close":"last","volume":"sum"
    }).dropna()
    if len(df15) < ATR_PERIOD + 3: return None
    ha15 = heiken_ashi(df15)
    ha15 = calc_supertrend(ha15, ATR_PERIOD, MULTIPLIER)
    d = ha15["direction"].iloc[-1]
    return int(d) if not np.isnan(d) else None

# ══════════════════════════════════════════════════════
# 📊  SIGNAL GRADER
#
#   Normal      → Supertrend crossover only (1 condition)
#   Strong      → + Gap clear + Volume ≥ 1.5× avg + VWAP side (3 more)
#   Very Strong → + RSI not extreme + 15-min agrees (2 more)
# ══════════════════════════════════════════════════════

def grade_signal(signal, df1):
    """
    Returns "normal" | "strong" | "very_strong"
    Never returns None — crossover always = at least Normal.
    """
    is_buy = "BUY" in signal

    # ── 3 conditions for Strong ────────────────────────
    # C1: not in gap window
    gap_ok = not in_gap_window()

    # C2: volume spike
    vols   = df1["volume"]
    avg_v  = vols.iloc[-21:-1].mean() if len(vols) > 21 else vols.mean()
    vol_ok = float(vols.iloc[-1]) >= avg_v * VOLUME_MULT

    # C3: correct VWAP side
    vwap     = calc_vwap(df1)
    ltp      = float(df1["close"].iloc[-1])
    vwap_ok  = (is_buy and ltp > vwap) or (not is_buy and ltp < vwap)

    strong = gap_ok and vol_ok and vwap_ok

    if not strong:
        return "normal"

    # ── 2 more conditions for Very Strong ─────────────
    # C4: RSI not extreme
    rsi    = calc_rsi(df1["close"], RSI_PERIOD)
    rsi_ok = not (is_buy and rsi > RSI_OB) and not (not is_buy and rsi < RSI_OS)

    # C5: 15-min Supertrend agrees
    dir15  = get_15min_dir(df1)
    mtf_ok = dir15 is not None and dir15 == (-1 if is_buy else 1)

    if rsi_ok and mtf_ok:
        return "very_strong"

    return "strong"

# ══════════════════════════════════════════════════════
# 📦  CANDLE STORE + STATE
# ══════════════════════════════════════════════════════

candle_store   = defaultdict(list)
last_closed_ts = {}
last_signal    = {}   # key → last sent signal string to avoid duplicates
lock           = threading.Lock()

def seed_candles():
    print("\n📥 Seeding today's 1-min candles...")
    today  = datetime.now().strftime("%Y-%m-%d")
    seeded = 0
    for stock in WATCHLIST:
        sym = stock["symbol"]
        key = stock["key"]
        candles = []

        # Try intraday first
        url = f"https://api.upstox.com/v2/historical-candle/intraday/{key}/1minute"
        try:
            r = requests.get(url, headers=REST_H, timeout=10)
            if r.status_code == 200:
                candles = r.json().get("data", {}).get("candles", [])
        except Exception:
            pass

        # Fallback: historical today
        if not candles:
            url = f"https://api.upstox.com/v2/historical-candle/{key}/1minute/{today}/{today}"
            try:
                r = requests.get(url, headers=REST_H, timeout=10)
                if r.status_code == 200:
                    candles = r.json().get("data", {}).get("candles", [])
            except Exception:
                pass

        if candles:
            store = []
            for c in candles:
                ts = pd.to_datetime(c[0]).replace(tzinfo=None).replace(second=0, microsecond=0)
                store.append({"ts": ts, "open": float(c[1]), "high": float(c[2]),
                               "low": float(c[3]), "close": float(c[4]), "vol": float(c[5])})
            store.sort(key=lambda x: x["ts"])
            candle_store[key] = store[-250:]
            if store:
                last_closed_ts[key] = store[-1]["ts"]
            print(f"  [{sym}] ✅ {len(store)} bars")
            seeded += 1
        else:
            print(f"  [{sym}] ⚠️  No seed data")

    print(f"  Seeded {seeded}/{len(WATCHLIST)} stocks\n")

# ══════════════════════════════════════════════════════
# 🔍  PROCESS 1-MIN BAR CLOSE → check 3-min → grade → alert
# ══════════════════════════════════════════════════════

def on_1min_closed(key, closed_ts):
    stock = KEY_TO_STOCK.get(key)
    if not stock:
        return

    with lock:
        store = list(candle_store[key])

    if len(store) < ATR_PERIOD + 5:
        return

    # Build 1-min df
    df1 = pd.DataFrame(store, columns=["ts","open","high","low","close","vol"])
    df1.rename(columns={"vol": "volume"}, inplace=True)
    df1.set_index("ts", inplace=True)
    df1.sort_index(inplace=True)
    df1 = df1[~df1.index.duplicated(keep="last")].astype(float)

    # 3-min (closed bars only)
    df3 = df1.resample("3T").agg({
        "open":"first","high":"max","low":"min","close":"last","volume":"sum"
    }).dropna()

    if closed_ts < df3.index[-1] + timedelta(minutes=3):
        df3 = df3.iloc[:-1]          # last 3-min bar still forming — drop it

    if len(df3) < ATR_PERIOD + 3:
        return

    ha3 = heiken_ashi(df3)
    ha3 = calc_supertrend(ha3, ATR_PERIOD, MULTIPLIER)

    if len(ha3) < 3:
        return

    prev_dir = ha3["direction"].iloc[-2]
    curr_dir = ha3["direction"].iloc[-1]
    bar_ts   = ha3.index[-1]

    if np.isnan(prev_dir) or np.isnan(curr_dir):
        return

    # Crossover?
    if   curr_dir == -1 and prev_dir ==  1: raw = "BUY"
    elif curr_dir ==  1 and prev_dir == -1: raw = "SELL"
    else:                                    return

    # Deduplicate
    if raw == last_signal.get(key):
        return
    last_signal[key] = raw

    # Grade the signal
    grade = grade_signal(raw, df1)

    # Send clean alert
    sym = stock["symbol"]
    send_signal_alert(sym, grade, raw, bar_ts)

    grade_label = {"normal": "Normal", "strong": "Strong", "very_strong": "Very Strong"}[grade]
    print(f"  ✅ [{sym}] {raw} | {grade_label} | bar={bar_ts.strftime('%H:%M')}")

# ══════════════════════════════════════════════════════
# 📨  WEBSOCKET MESSAGE HANDLER
# ══════════════════════════════════════════════════════

def on_message(message):
    try:
        feeds = message.get("feeds", {})
        for key, feed_data in feeds.items():
            if key not in KEY_TO_STOCK:
                continue

            ff       = feed_data.get("fullFeed", feed_data.get("ff", {}))
            mff      = ff.get("marketFF", {})
            ohlc_arr = mff.get("marketOHLC", {}).get("ohlc", [])

            if not ohlc_arr:
                continue

            i1 = [c for c in ohlc_arr if c.get("interval") == "I1"]
            if len(i1) < 2:
                continue

            prev  = i1[1]
            ts_ms = prev.get("ts")
            if not ts_ms:
                continue

            pc_ts = datetime.fromtimestamp(int(ts_ms) / 1000).replace(second=0, microsecond=0)

            if last_closed_ts.get(key) == pc_ts:
                continue                              # same bar — nothing new

            last_closed_ts[key] = pc_ts

            bar = {
                "ts":    pc_ts,
                "open":  float(prev.get("open",  0)),
                "high":  float(prev.get("high",  0)),
                "low":   float(prev.get("low",   0)),
                "close": float(prev.get("close", 0)),
                "vol":   float(prev.get("vol",   0)),
            }

            with lock:
                store = candle_store[key]
                if store and store[-1]["ts"] == pc_ts:
                    store[-1] = bar
                else:
                    store.append(bar)
                if len(store) > 250:
                    candle_store[key] = store[-250:]

            sym = KEY_TO_STOCK[key]["symbol"]
            print(f"  [{sym}] bar {pc_ts.strftime('%H:%M')} "
                  f"O={bar['open']} H={bar['high']} L={bar['low']} C={bar['close']}")

            threading.Thread(
                target=on_1min_closed,
                args=(key, pc_ts),
                daemon=True
            ).start()

    except Exception as e:
        import traceback
        print(f"  ⚠️ {e}")
        traceback.print_exc()

# ══════════════════════════════════════════════════════
# 🔌  WEBSOCKET — Upstox MarketDataStreamerV3
#   Pushes live tick data including 1-min OHLC
#   mode="full" → interval "I1" candle on every tick
#   This replaces polling completely — zero delay
# ══════════════════════════════════════════════════════

def start_streamer():
    config = upstox_client.Configuration()
    config.access_token = ACCESS_TOKEN
    streamer = upstox_client.MarketDataStreamerV3(upstox_client.ApiClient(config))

    def on_open():
        print("  ✅ WebSocket connected")
        streamer.subscribe(ALL_KEYS, "full")
        send_telegram(
            f"✅ <b>Signal Bot Live</b>  |  {len(WATCHLIST)} stocks\n"
            f"📶 Normal  |  📶📶 Strong  |  📶📶📶 Very Strong\n"
            f"🕒 {datetime.now().strftime('%d %b %Y  %H:%M:%S IST')}"
        )

    def on_close():
        print("  🔌 WS closed — reconnecting...")
        send_telegram("🔌 Disconnected — reconnecting...")

    def on_error(err):
        print(f"  ❌ {err}")

    streamer.on("open",    on_open)
    streamer.on("message", on_message)
    streamer.on("close",   on_close)
    streamer.on("error",   on_error)
    streamer.connect()

# ══════════════════════════════════════════════════════
# ✅  TOKEN
# ══════════════════════════════════════════════════════

def validate_token():
    try:
        r = requests.get("https://api.upstox.com/v2/user/profile",
                         headers=REST_H, timeout=10)
        if r.status_code == 200:
            u = r.json().get("data", {})
            print(f"✅ Token OK — {u.get('user_name')} ({u.get('email')})")
            return True
        print(f"❌ Token error {r.status_code}: {r.text[:100]}")
        send_telegram(f"⚠️ Token expired. Regenerate at upstox.com/developer/apps")
        return False
    except Exception as e:
        print(f"❌ {e}")
        return False

# ══════════════════════════════════════════════════════
# 🚀  MAIN
# ══════════════════════════════════════════════════════

print("=" * 55)
print("  📊  NSE SIGNAL BOT — 3 Signal Types")
print(f"  ⚙️   Supertrend({ATR_PERIOD},{MULTIPLIER}) | 3-Min HA")
print(f"  ⚡  WebSocket — live ticks, zero REST delay")
print()
print("  📶       Normal      → Supertrend crossover")
print("  📶📶     Strong      → + Gap + Volume + VWAP")
print("  📶📶📶   Very Strong → + RSI + 15-Min MTF")
print("=" * 55)

if not validate_token():
    exit(1)

send_telegram(
    f"🤖 <b>NSE Signal Bot Started</b>\n"
    f"📊 {len(WATCHLIST)} stocks  |  3-Min HA Supertrend\n"
    f"📶 Normal  ·  📶📶 Strong  ·  📶📶📶 Very Strong\n"
    f"⏰ NSE: Mon–Fri  09:15–15:30 IST\n"
    f"🕒 {datetime.now().strftime('%d %b %Y  %H:%M:%S IST')}"
)

if not is_nse_open():
    send_telegram(f"💤 Market closed. Opens: {next_open_str()}")
    print(f"\n💤 Market closed — opens {next_open_str()}")
    while not is_nse_open():
        time.sleep(30)

seed_candles()

# ── Auto-reconnect loop ──
while True:
    try:
        if not is_nse_open():
            send_telegram(f"💤 Market closed. Next: {next_open_str()}")
            print(f"\n💤 Closed — waiting...")
            while not is_nse_open():
                time.sleep(30)
            last_signal.clear()
            last_closed_ts.clear()
            candle_store.clear()
            seed_candles()
            print("🟢 Market open — starting WebSocket")

        start_streamer()   # blocks until WebSocket drops

        if is_nse_open():
            print("  🔄 Reconnecting in 5s...")
            time.sleep(5)

    except KeyboardInterrupt:
        print("\n🛑 Stopped.")
        send_telegram("🛑 Signal bot stopped.")
        break
    except Exception as e:
        import traceback
        print(f"❌ {e}")
        traceback.print_exc()
        time.sleep(10)