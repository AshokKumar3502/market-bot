"""
📊 WATCHLIST SIGNAL SCANNER
Select stocks by number → get last 5 Supertrend signals exactly matching TradingView
Indicator: Supertrend(10, 3.0) on 3-Min Heiken Ashi
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ══════════════════════════════════════════════════
# 🔐 CONFIG — update token daily
# ══════════════════════════════════════════════════

ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiIyQkNCNzQiLCJqdGkiOiI2OTliZGE5MTdmODBmOTFjMDgxNWM2YjgiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6dHJ1ZSwiaWF0IjoxNzcxODIxNzEzLCJpc3MiOiJ1ZGFwaS1nYXRld2F5LXNlcnZpY2UiLCJleHAiOjE3NzE4ODQwMDB9.XeGw4z7s9Hyqlsry3beozoqiLyUNP3l9ssqacyElKio"

ATR_PERIOD = 10
MULTIPLIER = 3.0
HEADERS    = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Accept": "application/json"}

# ══════════════════════════════════════════════════
# 📋 WATCHLIST
# ══════════════════════════════════════════════════

WATCHLIST = [
    {"no":  1, "symbol": "PAGEIND",    "name": "Page Industries",        "instrument_key": "NSE_EQ|INE761H01022"},
    {"no":  2, "symbol": "SHREECEM",   "name": "Shree Cement",           "instrument_key": "NSE_EQ|INE070A01015"},
    {"no":  3, "symbol": "MARUTI",     "name": "Maruti Suzuki",          "instrument_key": "NSE_EQ|INE585B01010"},
    {"no":  4, "symbol": "SOLARINDS",  "name": "Solar Industries",       "instrument_key": "NSE_EQ|INE343H01029"},
    {"no":  5, "symbol": "PAYTM",      "name": "Paytm (One97 Comm)",     "instrument_key": "NSE_EQ|INE982J01020"},
    {"no":  6, "symbol": "BOSCHLTD",   "name": "Bosch Ltd",              "instrument_key": "NSE_EQ|INE323A01026"},
    {"no":  7, "symbol": "DIXON",      "name": "Dixon Technologies",     "instrument_key": "NSE_EQ|INE935N01020"},
    {"no":  8, "symbol": "ULTRACEMCO", "name": "UltraTech Cement",       "instrument_key": "NSE_EQ|INE481G01011"},
    {"no":  9, "symbol": "JIOFIN",     "name": "Jio Financial Services", "instrument_key": "NSE_EQ|INE758T01015"},
    {"no": 10, "symbol": "OFSS",       "name": "Oracle Fin. Services",   "instrument_key": "NSE_EQ|INE881D01027"},
    {"no": 11, "symbol": "POLYCAB",    "name": "Polycab India",          "instrument_key": "NSE_EQ|INE455K01017"},
    {"no": 12, "symbol": "ABB",        "name": "ABB India",              "instrument_key": "NSE_EQ|INE117A01022"},
    {"no": 13, "symbol": "DIVISLAB",   "name": "Divi's Laboratories",    "instrument_key": "NSE_EQ|INE361B01024"},
]

# ══════════════════════════════════════════════════
# 📡 FETCH
# ══════════════════════════════════════════════════

def fetch_day(instrument_key, date_str):
    url = f"https://api.upstox.com/v2/historical-candle/{instrument_key}/1minute/{date_str}/{date_str}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json().get("data", {}).get("candles", [])
        elif r.status_code == 401:
            print("  ❌ Token expired! Regenerate at upstox.com/developer/apps")
    except Exception as e:
        print(f"  ⚠️  {date_str} fetch error: {e}")
    return []

def fetch_intraday(instrument_key):
    url = f"https://api.upstox.com/v2/historical-candle/intraday/{instrument_key}/1minute"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json().get("data", {}).get("candles", [])
    except:
        pass
    return []

def collect_candles(instrument_key, symbol):
    all_c = []
    days_fetched = 0
    for d in range(1, 20):
        date = (datetime.now() - timedelta(days=d)).strftime("%Y-%m-%d")
        c    = fetch_day(instrument_key, date)
        if c:
            all_c  = c + all_c
            days_fetched += 1
            print(f"    {date} → {len(c)} candles")
        if days_fetched >= 10:
            break
    # today + intraday
    c = fetch_day(instrument_key, datetime.now().strftime("%Y-%m-%d"))
    if c:
        all_c += c
        print(f"    {datetime.now().strftime('%Y-%m-%d')} (today) → {len(c)} candles")
    c = fetch_intraday(instrument_key)
    if c:
        all_c += c
        print(f"    intraday (live) → {len(c)} candles")
    return all_c

def build_df(candles):
    cols = ["datetime","open","high","low","close","volume"]
    if candles and len(candles[0]) == 7:
        cols.append("oi")
    df = pd.DataFrame(candles, columns=cols)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)
    return df[["open","high","low","close","volume"]].astype(float)

# ══════════════════════════════════════════════════
# 📈 INDICATOR — exact TradingView logic
# ══════════════════════════════════════════════════

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
    """
    TradingView ta.supertrend() exact logic:
      direction = -1 → BULLISH (green, ST line below price)
      direction = +1 → BEARISH (red,   ST line above price)
    BUY  signal: direction flips  1 → -1
    SELL signal: direction flips -1 →  1
    """
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
        # band locking
        lo[i] = rl[i] if (rl[i] > lo[i-1] or cl[i-1] < lo[i-1]) else lo[i-1]
        up[i] = ru[i] if (ru[i] < up[i-1] or cl[i-1] > up[i-1]) else up[i-1]
        # direction
        if di[i-1] == 1:
            di[i] = -1 if cl[i] > up[i-1] else 1
        else:
            di[i] =  1 if cl[i] < lo[i-1] else -1
        st[i] = lo[i] if di[i] == -1 else up[i]

    ha = ha.copy()
    ha["direction"]  = di
    ha["supertrend"] = st
    return ha

def get_all_signals(ha):
    signals = []
    for i in range(1, len(ha)):
        pd_ = ha["direction"].iloc[i-1]
        cd_ = ha["direction"].iloc[i]
        if np.isnan(pd_) or np.isnan(cd_):
            continue
        if cd_ == -1 and pd_ == 1:
            signals.append({"time": ha.index[i], "signal": "BUY  🟢", "type": "BUY",
                            "ha_close": round(float(ha["close"].iloc[i]), 2),
                            "supertrend": round(float(ha["supertrend"].iloc[i]), 2)})
        elif cd_ == 1 and pd_ == -1:
            signals.append({"time": ha.index[i], "signal": "SELL 🔴", "type": "SELL",
                            "ha_close": round(float(ha["close"].iloc[i]), 2),
                            "supertrend": round(float(ha["supertrend"].iloc[i]), 2)})
    return signals

# ══════════════════════════════════════════════════
# 📊 RUN ANALYSIS FOR ONE STOCK
# ══════════════════════════════════════════════════

def analyse_stock(stock):
    sym  = stock["symbol"]
    name = stock["name"]
    key  = stock["instrument_key"]

    print(f"\n{'─'*60}")
    print(f"  📥 Fetching {sym} — {name}")
    print(f"{'─'*60}")

    raw = collect_candles(key, sym)
    if not raw:
        print(f"  ❌ No data for {sym}. Token may be expired.")
        return

    df = build_df(raw)
    df = df[~df.index.duplicated(keep="last")]
    df.sort_index(inplace=True)
    print(f"  Total 1-min bars : {len(df)}")

    df3 = df.resample("3T").agg({
        "open":"first","high":"max",
        "low":"min","close":"last","volume":"sum"
    }).dropna()
    print(f"  3-min bars       : {len(df3)}")

    if len(df3) < ATR_PERIOD + 10:
        print(f"  ❌ Not enough bars ({len(df3)}). Need {ATR_PERIOD + 10}+.")
        return

    ha       = heiken_ashi(df3)
    ha       = calc_supertrend(ha, ATR_PERIOD, MULTIPLIER)
    signals  = get_all_signals(ha)
    last5    = signals[-5:] if len(signals) >= 5 else signals

    # ── Current state ──
    last_closed = ha.iloc[-2]   # -2 = last fully closed bar (not forming)
    curr_dir    = int(last_closed["direction"])
    trend_str   = "BULLISH 📈" if curr_dir == -1 else "BEARISH 📉"
    curr_close  = round(float(last_closed["close"]), 2)
    curr_st     = round(float(last_closed["supertrend"]), 2)
    curr_time   = ha.index[-2].strftime("%d %b %Y  %H:%M")

    # ── Print results ──
    print(f"\n  ╔{'═'*57}╗")
    print(f"  ║  📊 {sym} — {name:<42}║")
    print(f"  ║  ⚙️  Supertrend({ATR_PERIOD}, {MULTIPLIER}) | 3-Min Heiken Ashi{' '*14}║")
    print(f"  ╠{'═'*57}╣")
    print(f"  ║  {'#':<3} {'Date & Time':<22} {'Signal':<10} {'HA Close':>9} {'ST Line':>9} ║")
    print(f"  ╠{'─'*57}╣")

    if not last5:
        print(f"  ║  No signals found in available data{' '*21}║")
    else:
        for idx, s in enumerate(last5, 1):
            t_str = s["time"].strftime("%d %b %y  %H:%M")
            sig   = s["signal"]
            hac   = str(s["ha_close"])
            stv   = str(s["supertrend"])
            print(f"  ║  {idx:<3} {t_str:<22} {sig:<10} {hac:>9} {stv:>9} ║")

    print(f"  ╠{'═'*57}╣")
    print(f"  ║  CURRENT : {trend_str:<16} HA: {curr_close:<10} ST: {curr_st:<7}║")
    print(f"  ║  Bar Time: {curr_time:<46}║")
    print(f"  ╚{'═'*57}╝")

# ══════════════════════════════════════════════════
# 🖥️  INTERACTIVE MENU
# ══════════════════════════════════════════════════

def print_menu():
    print("\n" + "═"*60)
    print("  📊  SUPERTREND SIGNAL SCANNER  |  3-Min HA")
    print(f"  ⚙️   Supertrend({ATR_PERIOD}, {MULTIPLIER})  |  Last 5 Signals per Stock")
    print("═"*60)
    print(f"  {'No.':<5} {'Symbol':<12} {'Company Name'}")
    print(f"  {'─'*55}")
    for s in WATCHLIST:
        print(f"  {s['no']:<5} {s['symbol']:<12} {s['name']}")
    print(f"  {'─'*55}")
    print(f"  {len(WATCHLIST)+1:<5} {'ALL':<12} Scan all stocks")
    print(f"  {0:<5} {'EXIT':<12} Quit")
    print("═"*60)

def parse_input(raw):
    """
    Accept formats:
      Single  : 1
      Multiple: 1,3,7
      Range   : 1-5
      All     : all / 0
    """
    raw = raw.strip().lower()
    if raw in ("0", "exit", "quit", "q"):
        return "exit"
    if raw in ("all", str(len(WATCHLIST)+1)):
        return list(range(1, len(WATCHLIST)+1))

    selected = set()
    for part in raw.split(","):
        part = part.strip()
        if "-" in part:
            try:
                a, b = part.split("-")
                selected.update(range(int(a), int(b)+1))
            except:
                print(f"  ⚠️  Invalid range: {part}")
        elif part.isdigit():
            selected.add(int(part))
        else:
            print(f"  ⚠️  Invalid input: {part}")

    valid = [n for n in sorted(selected) if 1 <= n <= len(WATCHLIST)]
    invalid = [n for n in selected if not (1 <= n <= len(WATCHLIST))]
    if invalid:
        print(f"  ⚠️  Ignored out-of-range numbers: {invalid}")
    return valid

# ══════════════════════════════════════════════════
# 🚀 MAIN
# ══════════════════════════════════════════════════

print("\n" + "█"*60)
print("  🚀  WATCHLIST SIGNAL SCANNER")
print("  Supertrend(10, 3.0) | 3-Min Heiken Ashi")
print("  Matches TradingView indicator exactly")
print("█"*60)

while True:
    print_menu()
    print("\n  Enter stock number(s) to scan:")
    print("  Examples:  3        → single stock")
    print("             1,3,7    → multiple stocks")
    print("             1-5      → range")
    print("             all      → all 13 stocks")
    print("             0        → exit\n")

    try:
        raw      = input("  Your choice: ")
        selected = parse_input(raw)

        if selected == "exit":
            print("\n  👋 Goodbye!\n")
            break

        if not selected:
            print("  ⚠️  No valid stocks selected. Try again.")
            continue

        stocks_to_scan = [s for s in WATCHLIST if s["no"] in selected]
        print(f"\n  ✅ Scanning {len(stocks_to_scan)} stock(s): "
              f"{', '.join(s['symbol'] for s in stocks_to_scan)}")

        for stock in stocks_to_scan:
            analyse_stock(stock)

        print(f"\n\n  ✅ Done scanning {len(stocks_to_scan)} stock(s).")
        print("  Press ENTER to go back to menu or type 0 to exit.")
        cont = input("  > ").strip()
        if cont == "0":
            print("\n  👋 Goodbye!\n")
            break

    except KeyboardInterrupt:
        print("\n\n  👋 Exited.\n")
        break
    except Exception as e:
        print(f"\n  ❌ Error: {e}")
        import traceback; traceback.print_exc()