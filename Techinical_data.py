"""
╔══════════════════════════════════════════════════════════════════╗
║   INSTITUTIONAL MARKET INTELLIGENCE ENGINE                       ║
║   Module: institutional_edge.py                                  ║
╠══════════════════════════════════════════════════════════════════╣
║   Covers ALL 8 Institutional Dimensions:                         ║
║   1. DOM — Real Order Book (5-level Bid/Ask Depth)               ║
║   2. Order Flow — Delta, Imbalance, Absorption                   ║
║   3. Institutional Positioning — Block trades, FII proxy         ║
║   4. Macro Clock — Market session time behavior                  ║
║   5. Liquidity Engineering — Stop hunts, equal highs/lows        ║
║   6. Options OI — Max Pain, PCR, Gamma zones                     ║
║   7. Time-Based Behavior — Session analysis (9:15/midday/close)  ║
║   8. Psychology Gauge — Fear/Greed, FOMO, Trap detection         ║
╠══════════════════════════════════════════════════════════════════╣
║   Import into watchlist_intelligence.py OR run standalone        ║
║   Usage: python institutional_edge.py --stock DIXON              ║
╚══════════════════════════════════════════════════════════════════╝

  What Upstox API CAN provide (used here):
  ✅ 5-level Bid/Ask DOM (depth) from full market quote
  ✅ Total buy qty vs sell qty → order flow delta
  ✅ Volume spikes → block deal detection
  ✅ 1-minute candles → intraday session analysis
  ✅ Options chain (PCR, OI, Max Pain) for NSE_INDEX linked stocks
  ✅ OHLC for liquidity zone mapping

  What Upstox API CANNOT provide (hard limits — explained):
  ❌ True tick-by-tick footprint (who hit bid / lifted ask)
  ❌ Dark pool / block deal exact counterparties
  ❌ Real-time FII/DII flows (NSE publishes EOD only)
  ❌ Iceberg order detection (exchange hides these)
  ❌ Gamma exposure (requires options MM book data)
"""

import argparse
import requests
import sys
from datetime import datetime, timedelta, time as dtime

try:
    import pandas as pd
    import numpy as np
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

# ── Copy your token here ──────────────────────────────────────
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiIyQkNCNzQiLCJqdGkiOiI2OTlkMjQ5OTA0NTQxZTc2ZWRkMzMzODMiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6dHJ1ZSwiaWF0IjoxNzcxOTA2MjAxLCJpc3MiOiJ1ZGFwaS1nYXRld2F5LXNlcnZpY2UiLCJleHAiOjE3NzE5NzA0MDB9.k8M6pdpFGofqQUBiyDa0teyS3LqPq9afMSQ2pO0ZWss"

BASE_URL = "https://api.upstox.com/v2"
DIVIDER  = "═" * 68
THIN     = "─" * 68

# Watchlist (same as watchlist_intelligence.py)
WATCHLIST = {
    "PAGEIND":   {"key": "NSE_EQ|INE761H01022", "name": "Page Industries",           "fo_key": None},
    "SHREECEM":  {"key": "NSE_EQ|INE070A01015", "name": "Shree Cement",               "fo_key": None},
    "MARUTI":    {"key": "NSE_EQ|INE585B01010", "name": "Maruti Suzuki",              "fo_key": "NSE_FO"},
    "SOLARINDS": {"key": "NSE_EQ|INE03D201019", "name": "Solar Industries",           "fo_key": None},
    "PAYTM":     {"key": "NSE_EQ|INE982J01020", "name": "Paytm",                      "fo_key": None},
    "BOSCHLTD":  {"key": "NSE_EQ|INE323A01026", "name": "Bosch Ltd",                  "fo_key": None},
    "DIXON":     {"key": "NSE_EQ|INE935N01012", "name": "Dixon Technologies",         "fo_key": None},
    "ULTRACEMCO":{"key": "NSE_EQ|INE481G01011", "name": "UltraTech Cement",           "fo_key": "NSE_FO"},
    "JIOFIN":    {"key": "NSE_EQ|INE758T01015", "name": "Jio Financial Services",     "fo_key": None},
    "OFSS":      {"key": "NSE_EQ|INE881D01027", "name": "Oracle Financial Services",  "fo_key": None},
    "POLYCAB":   {"key": "NSE_EQ|INE455K01017", "name": "Polycab India",              "fo_key": None},
    "ABB":       {"key": "NSE_EQ|INE117A01022", "name": "ABB India",                  "fo_key": None},
    "DIVISLAB":  {"key": "NSE_EQ|INE361B01024", "name": "Divi's Laboratories",        "fo_key": "NSE_FO"},
}

# NIFTY 50 instrument key for index options context
NIFTY_KEY = "NSE_INDEX|Nifty 50"


# ═══════════════════════════════════════════════════════════════
#  DISPLAY HELPERS
# ═══════════════════════════════════════════════════════════════

def clr(t, c): return f"\033[{c}m{t}\033[0m"
def green(t):  return clr(t, "92")
def red(t):    return clr(t, "91")
def yellow(t): return clr(t, "93")
def cyan(t):   return clr(t, "96")
def bold(t):   return clr(t, "1")
def dim(t):    return clr(t, "2")
def magenta(t):return clr(t, "95")

def section(title):
    print(f"\n{THIN}")
    print(f"  {bold(cyan(title))}")
    print(THIN)

def tbl(rows, headers):
    if HAS_TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))
    else:
        widths = [max(len(str(r[i])) for r in ([headers] + list(rows))) for i in range(len(headers))]
        fmt = "  ".join(f"{{:<{w}}}" for w in widths)
        print(fmt.format(*headers))
        print("  ".join("-"*w for w in widths))
        for r in rows:
            print(fmt.format(*[str(x) for x in r]))


# ═══════════════════════════════════════════════════════════════
#  API HELPERS
# ═══════════════════════════════════════════════════════════════

def hdrs(token):
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

def api_get(token, endpoint, params=None):
    try:
        r = requests.get(f"{BASE_URL}{endpoint}", headers=hdrs(token), params=params, timeout=12)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError:
        print(red(f"  ❌ HTTP {r.status_code}: {r.text[:100]}"))
        return None
    except Exception as e:
        print(red(f"  ❌ Error: {e}"))
        return None

def fetch_full_quote(token, instrument_key):
    """Full quote includes DOM depth (5 bid/ask levels)."""
    data = api_get(token, "/market-quote/quotes", {"instrument_key": instrument_key})
    if data and data.get("status") == "success":
        d = data.get("data", {})
        k = list(d.keys())[0] if d else None
        return d.get(k, {}) if k else {}
    return {}

def fetch_intraday_candles(token, instrument_key, interval="1minute", days=1):
    """1-minute candles for intraday session analysis."""
    to_dt = datetime.today()
    fr_dt = to_dt - timedelta(days=days + 3)
    endpoint = f"/historical-candle/intraday/{instrument_key}/{interval}"
    data = api_get(token, endpoint)
    if not data or data.get("status") != "success":
        # fallback to historical
        to_str = to_dt.strftime("%Y-%m-%d")
        fr_str = fr_dt.strftime("%Y-%m-%d")
        endpoint2 = f"/historical-candle/{instrument_key}/{interval}/{to_str}/{fr_str}"
        data = api_get(token, endpoint2)
    if not data or data.get("status") != "success":
        return None
    candles = data.get("data", {}).get("candles", [])
    if not candles or not HAS_PANDAS:
        return None
    df = pd.DataFrame(candles, columns=["ts", "open", "high", "low", "close", "volume", "oi"])
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts").reset_index(drop=True)
    return df

def fetch_daily_candles(token, instrument_key, days=60):
    to_dt  = datetime.today()
    fr_dt  = to_dt - timedelta(days=days + 20)
    to_str = to_dt.strftime("%Y-%m-%d")
    fr_str = fr_dt.strftime("%Y-%m-%d")
    endpoint = f"/historical-candle/{instrument_key}/day/{to_str}/{fr_str}"
    data = api_get(token, endpoint)
    if not data or data.get("status") != "success":
        return None
    candles = data.get("data", {}).get("candles", [])
    if not candles or not HAS_PANDAS:
        return None
    df = pd.DataFrame(candles, columns=["ts", "open", "high", "low", "close", "volume", "oi"])
    df["ts"] = pd.to_datetime(df["ts"])
    return df.sort_values("ts").reset_index(drop=True)

def fetch_option_chain(token, index_key, expiry_date):
    """Fetch full option chain (PCR, OI, Max Pain)."""
    data = api_get(token, "/option/chain", {
        "instrument_key": index_key,
        "expiry_date": expiry_date
    })
    if data and data.get("status") == "success":
        return data.get("data", [])
    return []

def fetch_option_expiries(token, index_key):
    """Get available expiry dates."""
    data = api_get(token, "/option/contract", {"instrument_key": index_key})
    if data and data.get("status") == "success":
        contracts = data.get("data", [])
        expiries = sorted(set(c.get("expiry") for c in contracts if c.get("expiry")))
        return expiries
    return []


# ═══════════════════════════════════════════════════════════════
#  1. DOM — DEPTH OF MARKET ANALYSIS
# ═══════════════════════════════════════════════════════════════

def analyze_dom(quote: dict):
    """
    Real Order Book Analysis.
    Upstox provides 5-level DOM via full market quote.
    We compute:
    - Bid/Ask imbalance
    - Wall detection (large stacked orders)
    - Absorption signal (price not moving despite large orders)
    """
    section("🏛️  [1] DOM — DEPTH OF MARKET (Order Book)")

    depth = quote.get("depth", {})
    bids  = depth.get("buy",  [])
    asks  = depth.get("sell", [])

    ltp = quote.get("last_price", 0)

    if not bids and not asks:
        print(red("  ❌ DOM data not available (market may be closed or no depth returned)."))
        print(dim("  💡 DOM is only meaningful during live market hours (9:15 AM – 3:30 PM IST)."))
        return

    print(f"\n  {'BIDS (Buy Side)':^35}  {'ASKS (Sell Side)':^35}")
    print(f"  {'─'*35}  {'─'*35}")
    print(f"  {'Orders':>8}  {'Qty':>12}  {'Price':>10}  {'Price':>10}  {'Qty':>12}  {'Orders':>8}")
    print(f"  {'─'*35}  {'─'*35}")

    total_bid_qty = 0
    total_ask_qty = 0
    bid_wall = None
    ask_wall = None
    BID_WALL_THRESHOLD = 50000  # Shares — adjust for stock liquidity

    for i in range(max(len(bids), len(asks))):
        b = bids[i] if i < len(bids) else {"quantity": 0, "price": 0, "orders": 0}
        a = asks[i] if i < len(asks) else {"quantity": 0, "price": 0, "orders": 0}

        b_qty = b.get("quantity", 0)
        a_qty = a.get("quantity", 0)
        total_bid_qty += b_qty
        total_ask_qty += a_qty

        b_flag = " ⚡WALL" if b_qty >= BID_WALL_THRESHOLD else ""
        a_flag = " ⚡WALL" if a_qty >= BID_WALL_THRESHOLD else ""
        if b_qty >= BID_WALL_THRESHOLD: bid_wall = b.get("price", 0)
        if a_qty >= BID_WALL_THRESHOLD: ask_wall = a.get("price", 0)

        b_str = green(f"{b['orders']:>8}  {b_qty:>12,}  ₹{b['price']:>9.2f}")
        a_str = red(f"₹{a['price']:>9.2f}  {a_qty:>12,}  {a['orders']:>8}")

        print(f"  {b_str}  {a_str}{a_flag}")

    print(f"  {'─'*35}  {'─'*35}")

    # Bid/Ask imbalance
    total = total_bid_qty + total_ask_qty
    bid_pct = (total_bid_qty / total * 100) if total > 0 else 50
    ask_pct = 100 - bid_pct

    print(f"\n  📊 ORDER FLOW IMBALANCE:")
    bar_len = 40
    bid_bar = int(bid_pct / 100 * bar_len)
    ask_bar = bar_len - bid_bar
    bar = green("█" * bid_bar) + red("█" * ask_bar)
    print(f"  BID [{bar}] ASK")
    print(f"  {green(f'Buy: {total_bid_qty:,} ({bid_pct:.1f}%)')}  {red(f'Sell: {total_ask_qty:,} ({ask_pct:.1f}%)')}")

    print(f"\n  📌 INTERPRETATION:")
    rows = []
    if bid_pct > 60:
        rows.append([green("DOM BIAS"),       green("BUY SIDE HEAVY"),   f"{bid_pct:.1f}% bid stacked — strong buying interest"])
    elif ask_pct > 60:
        rows.append([red("DOM BIAS"),         red("SELL SIDE HEAVY"),    f"{ask_pct:.1f}% ask stacked — distribution/selling pressure"])
    else:
        rows.append([yellow("DOM BIAS"),      yellow("BALANCED"),         "No dominant side — wait for absorption to resolve"])

    if bid_wall:
        rows.append([green("BID WALL"),       green(f"₹{bid_wall:.2f}"), "Large buy order — acts as strong support floor"])
    if ask_wall:
        rows.append([red("ASK WALL"),         red(f"₹{ask_wall:.2f}"),  "Large sell order — acts as resistance ceiling"])

    # Iceberg detection heuristic
    # If price is near bid wall but wall is NOT shrinking = iceberg (hidden refresh)
    rows.append([dim("Iceberg Orders"),   dim("⚠️  UNDETECTABLE"),  "Exchanges hide refreshed orders — monitor via DOM changes over time"])
    rows.append([dim("Hidden Liquidity"), dim("⚠️  UNDETECTABLE"),  "Dark pools, off-market blocks not visible in DOM"])

    tbl(rows, ["Signal", "Reading", "Interpretation"])


# ═══════════════════════════════════════════════════════════════
#  2. ORDER FLOW DELTA — CUMULATIVE DELTA PROXY
# ═══════════════════════════════════════════════════════════════

def analyze_order_flow(quote: dict, df_intraday):
    """
    True order flow requires tick data (who hit bid vs lifted ask).
    Upstox REST API gives candles only — no tick data.
    We compute the best available proxies:
    - Candle delta (close vs open direction × volume)
    - Cumulative delta over session
    - Bid/Ask absorption from DOM
    """
    section("⚡ [2] ORDER FLOW — CUMULATIVE DELTA & BID/ASK ABSORPTION")

    # From DOM
    tbq = quote.get("total_buy_quantity",  0) or 0
    tsq = quote.get("total_sell_quantity", 0) or 0
    ltp = quote.get("last_price", 0) or 0
    avg = quote.get("average_price", 0) or 0

    total = tbq + tsq
    if total > 0:
        buy_pct = tbq / total * 100
        raw_delta = tbq - tsq
        print(f"\n  📦 SESSION ORDER FLOW (from Exchange Pending Orders):")
        print(f"  Total Buy  Qty : {green(f'{tbq:>15,}')}")
        print(f"  Total Sell Qty : {red(f'{tsq:>15,}')}")
        print(f"  Raw Delta      : {green(f'+{raw_delta:,}') if raw_delta >= 0 else red(f'{raw_delta:,}')}")
        print(f"  Buy Side       : {green(f'{buy_pct:.1f}%') if buy_pct > 55 else (red(f'{buy_pct:.1f}%') if buy_pct < 45 else yellow(f'{buy_pct:.1f}%'))}")

        print(f"\n  📌 LTP ₹{ltp:.2f} vs Avg Price ₹{avg:.2f}")
        if avg > 0:
            if ltp > avg * 1.002:
                print(f"  {green('✅ Price above average — aggressive buyers lifting the ask (BUY PRESSURE)')}")
            elif ltp < avg * 0.998:
                print(f"  {red('⚠️  Price below average — aggressive sellers hitting the bid (SELL PRESSURE)')}")
            else:
                print(f"  {yellow('⚡ Price near average — balanced, watching for breakout direction')}")

    # Intraday candle delta (proxy for footprint)
    if df_intraday is not None and len(df_intraday) > 5:
        print(f"\n  📈 CANDLE DELTA (1-Minute Footprint Proxy):")
        print(dim("  [True footprint needs tick data — this is best REST-API approximation]"))

        df = df_intraday.copy()
        df["delta"]    = df.apply(lambda r: r["volume"] if r["close"] >= r["open"] else -r["volume"], axis=1)
        df["cum_delta"] = df["delta"].cumsum()

        # Session segments
        df["hour"] = df["ts"].dt.hour
        open_seg   = df[df["hour"].between(9, 10)]
        mid_seg    = df[df["hour"].between(11, 13)]
        close_seg  = df[df["hour"] >= 14]

        rows = []
        for label, seg in [("Opening (9:15–10:30)", open_seg),
                            ("Midday  (11:00–13:59)", mid_seg),
                            ("Closing (14:00–15:30)", close_seg)]:
            if len(seg) == 0:
                continue
            seg_delta = seg["delta"].sum()
            seg_vol   = seg["volume"].sum()
            bias = green("BUYING") if seg_delta > 0 else red("SELLING")
            rows.append([label, f"{seg_delta:+,}", f"{seg_vol:,}", bias])

        cum_now = df["cum_delta"].iloc[-1]
        tbl(rows, ["Session", "Delta (Volume)", "Total Volume", "Bias"])
        print(f"\n  Cumulative Session Delta: {green(f'+{cum_now:,.0f}') if cum_now >= 0 else red(f'{cum_now:,.0f}')}")
        print(dim("  +ve = net aggressive buying  |  -ve = net aggressive selling"))

    # Hard limits
    print(f"\n  {dim('─'*60)}")
    print(dim("  ⚠️  HARD LIMITS of REST API Order Flow:"))
    print(dim("     • Cannot see who hit bid vs lifted ask (requires tick-by-tick feed)"))
    print(dim("     • Cannot see true footprint candles (need Websocket + tick aggregation)"))
    print(dim("     • For full DOM: subscribe to Upstox WebSocket in FULL_D30 mode"))


# ═══════════════════════════════════════════════════════════════
#  3. INSTITUTIONAL POSITIONING
# ═══════════════════════════════════════════════════════════════

def analyze_institutional_positioning(df_daily, quote, sym):
    """
    Real FII/DII data is published by NSE at EOD.
    We provide:
    - Block trade proxies (volume spikes)
    - Price-volume divergence (smart money vs retail)
    - Delivery volume interpretation
    - EOD FII/DII where to fetch it
    """
    section("🏦 [3] INSTITUTIONAL POSITIONING")

    if df_daily is None or not HAS_PANDAS:
        print(red("  ❌ No daily candle data."))
        return

    close  = df_daily["close"]
    volume = df_daily["volume"]
    ltp    = quote.get("last_price") or close.iloc[-1]

    avg_vol_50 = volume.tail(50).mean()
    avg_vol_20 = volume.tail(20).mean()

    print(f"\n  📊 BLOCK TRADE DETECTION (Volume Spike Analysis):")
    rows = []

    # Last 20 days — flag anomalies
    recent = df_daily.tail(20).copy()
    recent["vol_ratio"] = recent["volume"] / avg_vol_50
    recent["direction"] = recent.apply(lambda r: "▲ UP" if r["close"] >= r["open"] else "▼ DOWN", axis=1)

    spike_days = recent[recent["vol_ratio"] >= 2.0]
    if len(spike_days) > 0:
        print(f"  {green(f'Found {len(spike_days)} high-volume days (≥2x avg) in last 20 sessions:')}")
        for _, row in spike_days.iterrows():
            dir_col = green(row["direction"]) if "UP" in row["direction"] else red(row["direction"])
            label = green("ACCUMULATION") if "UP" in row["direction"] else red("DISTRIBUTION")
            rows.append([
                str(row["ts"].date()),
                f"₹{row['close']:.2f}",
                f"{row['volume']:,.0f}",
                f"{row['vol_ratio']:.1f}x",
                dir_col,
                label
            ])
        tbl(rows, ["Date", "Close", "Volume", "vs Avg", "Direction", "Inst. Activity"])
    else:
        print(f"  {yellow('No major block activity in last 20 days — institutions quiet')}")

    # Price-Volume Divergence
    print(f"\n  📉 PRICE-VOLUME DIVERGENCE (Smart Money vs Retail):")
    pv_rows = []
    # Rising price + falling volume = distribution (smart money selling into retail buying)
    last5_price = close.tail(5).mean()
    prev5_price = close.iloc[-10:-5].mean()
    last5_vol   = volume.tail(5).mean()
    prev5_vol   = volume.iloc[-10:-5].mean()

    price_up  = last5_price > prev5_price
    vol_up    = last5_vol   > prev5_vol

    if price_up and vol_up:
        pv_rows.append([green("Price ▲ + Volume ▲"), green("CONFIRMED RALLY"),     "Institutions supporting the move — safe to follow"])
    elif price_up and not vol_up:
        pv_rows.append([yellow("Price ▲ + Volume ▼"), yellow("DISTRIBUTION RISK"), "Price rising on low vol — smart money selling to retail"])
    elif not price_up and vol_up:
        pv_rows.append([red("Price ▼ + Volume ▲"), red("PANIC / CAPITULATION"),   "High-vol drop — could be final flush before reversal"])
    else:
        pv_rows.append([dim("Price ▼ + Volume ▼"), dim("LACK OF INTEREST"),        "Low conviction — institutions not participating"])

    tbl(pv_rows, ["Pattern", "Interpretation", "Action"])

    # Delivery volume note
    print(f"\n  📦 DELIVERY VOLUME (FII/DII Proxy):")
    print(f"  {dim('Upstox does not expose delivery % directly via API.')}")
    print(f"  {bold('➤  Get real FII/DII flows from:')} ")
    print(f"  {cyan('  • NSE Bhav copy (EOD)  : https://www.nseindia.com/market-data/bulk-deals-block-deals')}")
    print(f"  {cyan('  • BSE bulk deals        : https://www.bseindia.com/markets/equity/EQReports/bulk-deals.aspx')}")
    print(f"  {cyan('  • NSE FII/DII daily     : https://www.nseindia.com/market-data/institutional-trading')}")
    print(f"  {cyan('  • SEBI block trade data : https://www.sebi.gov.in')}")


# ═══════════════════════════════════════════════════════════════
#  4 & 7. TIME-BASED INSTITUTIONAL BEHAVIOR
# ═══════════════════════════════════════════════════════════════

def analyze_time_behavior(df_intraday):
    """
    Institutions behave very differently by session.
    We show per-session volume/delta breakdown.
    """
    section("⏰ [4 & 7] TIME-BASED INSTITUTIONAL BEHAVIOR")

    now = datetime.now()
    ist_hour   = now.hour
    ist_minute = now.minute

    # Session classification
    print(f"\n  🕐 Current Time: {now.strftime('%H:%M:%S IST')}")
    print()

    sessions = [
        ("9:15 – 10:30",  "AGGRESSIVE OPEN",   "FII/algo algos fire — highest volatility, reversals common"),
        ("10:30 – 11:30", "DISCOVERY",          "True direction being established — watch volume confirmation"),
        ("11:30 – 13:00", "MIDDAY DRIFT",       "Low liquidity, choppy — institutions passive, avoid noise"),
        ("13:00 – 14:00", "PRE-CLOSE SETUP",    "Smart money repositioning before closing — watch for unusual vol"),
        ("14:00 – 15:00", "INSTITUTIONAL PUSH", "FII/mutual fund orders flow in — trend often accelerates"),
        ("15:00 – 15:30", "CLOSING AUCTION",    "Portfolio rebalancing, closing mark — reversals common"),
    ]

    rows = []
    for time_range, label, note in sessions:
        start_h = int(time_range.split(":")[0])
        start_m = int(time_range.split(":")[1].split("–")[0].strip())
        if ist_hour == start_h and ist_minute >= start_m:
            active = bold(green("◀ YOU ARE HERE"))
        elif ist_hour > start_h:
            active = dim("✓ PASSED")
        else:
            active = dim("⏳ UPCOMING")
        rows.append([time_range, bold(label), note, active])

    tbl(rows, ["Session", "Mode", "Institutional Behavior", "Status"])

    # Per-session analysis from intraday candles
    if df_intraday is not None and len(df_intraday) > 5:
        print(f"\n  📊 TODAY'S SESSION BREAKDOWN:")
        df = df_intraday.copy()
        df["hour"] = df["ts"].dt.hour

        seg_rows = []
        for label, h_start, h_end in [
            ("Open (9–10)", 9, 10),
            ("Mid (11–13)", 11, 13),
            ("Close (14–15)", 14, 15),
        ]:
            seg = df[df["hour"].between(h_start, h_end)]
            if len(seg) == 0:
                seg_rows.append([label, "-", "-", "-", dim("No data yet")])
                continue
            vol   = seg["volume"].sum()
            delta = seg.apply(lambda r: r["volume"] if r["close"] >= r["open"] else -r["volume"], axis=1).sum()
            hi    = seg["high"].max()
            lo    = seg["low"].min()
            bias  = green("BUYING") if delta > 0 else red("SELLING")
            seg_rows.append([label, f"{vol:,.0f}", f"{delta:+,.0f}", f"₹{lo:.2f}–₹{hi:.2f}", bias])

        tbl(seg_rows, ["Session", "Volume", "Net Delta", "Range", "Bias"])


# ═══════════════════════════════════════════════════════════════
#  5. LIQUIDITY ENGINEERING — STOP HUNTS & TRAP ZONES
# ═══════════════════════════════════════════════════════════════

def analyze_liquidity_zones(df_daily, df_intraday, ltp):
    """
    Institutions engineer liquidity:
    - Push to equal highs → trigger retail stop losses above
    - Grab liquidity → reverse sharply
    We detect: equal highs/lows, breakout traps, stop hunt zones
    """
    section("🎯 [5] LIQUIDITY ENGINEERING — STOP HUNTS & TRAP ZONES")

    if df_daily is None or not HAS_PANDAS:
        return

    highs = df_daily["high"].tail(30).values
    lows  = df_daily["low"].tail(30).values
    dates = df_daily["ts"].tail(30).values

    EQUAL_THRESHOLD = 0.003  # 0.3% = "equal" high/low

    # Find equal highs (where retail stops cluster)
    eq_highs = []
    for i in range(len(highs) - 1):
        for j in range(i + 1, len(highs)):
            if abs(highs[i] - highs[j]) / highs[i] < EQUAL_THRESHOLD:
                eq_highs.append(highs[j])

    eq_lows = []
    for i in range(len(lows) - 1):
        for j in range(i + 1, len(lows)):
            if abs(lows[i] - lows[j]) / lows[i] < EQUAL_THRESHOLD:
                eq_lows.append(lows[j])

    recent_high = df_daily["high"].tail(5).max()
    recent_low  = df_daily["low"].tail(5).min()
    swing_high  = df_daily["high"].tail(20).max()
    swing_low   = df_daily["low"].tail(20).min()

    print(f"\n  📌 LIQUIDITY POOL MAP:")
    rows = []

    # Above market — buy stops (where shorts stop out = fuel for push higher)
    rows.append([magenta("ABOVE MARKET (Buy Stops)"), "", ""])
    rows.append(["Equal Highs Zone", f"₹{max(eq_highs):.2f}" if eq_highs else "None found",
                 "Retail stops clustered here — institutions may sweep then reverse"])
    rows.append(["20D Swing High", f"₹{swing_high:.2f}",
                 "Key resistance — breakout above = stop hunt or real breakout?"])
    rows.append(["Recent 5D High", f"₹{recent_high:.2f}",
                 "Short-term stop cluster — watch for false breakout"])

    rows.append(["", "", ""])
    rows.append([f"{'─'*20} LTP ₹{ltp:.2f} {'─'*20}", "", ""])
    rows.append(["", "", ""])

    # Below market — sell stops (where longs stop out = fuel for push lower)
    rows.append([magenta("BELOW MARKET (Sell Stops)"), "", ""])
    rows.append(["Recent 5D Low", f"₹{recent_low:.2f}",
                 "Long stop cluster — institutions may sweep for liquidity"])
    rows.append(["20D Swing Low", f"₹{swing_low:.2f}",
                 "Major support — break below = stop hunt or true breakdown?"])
    rows.append(["Equal Lows Zone", f"₹{min(eq_lows):.2f}" if eq_lows else "None found",
                 "High-probability buy zone if swept and reclaimed"])

    tbl(rows, ["Zone", "Price Level", "Institutional Interpretation"])

    # Trap detection
    print(f"\n  🪤 BREAKOUT TRAP DETECTION:")
    trap_rows = []

    # If price recently broke above swing high but closed back below
    last_close = df_daily["close"].iloc[-1]
    last_high  = df_daily["high"].iloc[-1]
    if last_high > swing_high * 0.998 and last_close < swing_high:
        trap_rows.append([red("⚠️  BULL TRAP DETECTED"),
                          f"Price pierced ₹{swing_high:.2f} but closed below",
                          "Classic stop hunt — institutions grabbed stops, may reverse down"])
    elif df_daily["low"].iloc[-1] < swing_low * 1.002 and last_close > swing_low:
        trap_rows.append([green("✅ BEAR TRAP DETECTED"),
                          f"Price pierced ₹{swing_low:.2f} but closed above",
                          "Liquidity grab below — institutions may drive price up now"])
    else:
        trap_rows.append([yellow("🟡 NO TRAP NOW"),
                          "No recent sweep/rejection",
                          "Watch equal highs/lows for next sweep"])

    tbl(trap_rows, ["Pattern", "Evidence", "Implication"])


# ═══════════════════════════════════════════════════════════════
#  6. OPTIONS POSITIONING — MAX PAIN, PCR, GAMMA ZONES
# ═══════════════════════════════════════════════════════════════

def analyze_options(token, sym, ltp):
    """
    Options OI data tells you where institutions have positioned.
    - Max Pain = price where most options expire worthless
    - PCR = Put/Call ratio — market sentiment
    - Heavy Call OI = resistance zone
    - Heavy Put OI = support zone
    - Gamma squeeze zones = forced hedging at key strikes
    Uses NIFTY index chain as macro context for all stocks.
    """
    section("📊 [6] OPTIONS POSITIONING — MAX PAIN, PCR & GAMMA ZONES")
    print(dim("  [Using NIFTY index option chain as macro context]"))
    print(dim("  [Individual stock F&O available for: MARUTI, ULTRACEMCO, DIVISLAB]"))

    # Get next expiry
    expiries = fetch_option_expiries(token, NIFTY_KEY)
    if not expiries:
        print(red("  ❌ Could not fetch expiry dates."))
        return

    nearest_expiry = expiries[0]
    print(f"\n  📅 Analyzing expiry: {bold(cyan(nearest_expiry))}")

    chain = fetch_option_chain(token, NIFTY_KEY, nearest_expiry)
    if not chain:
        print(red("  ❌ Option chain data unavailable."))
        return

    if not HAS_PANDAS:
        print(red("  ❌ pandas required for options analysis."))
        return

    df_opt = pd.DataFrame([{
        "strike":      c.get("strike_price", 0),
        "call_oi":     c.get("call_options", {}).get("market_data", {}).get("oi", 0),
        "put_oi":      c.get("put_options",  {}).get("market_data", {}).get("oi", 0),
        "call_vol":    c.get("call_options", {}).get("market_data", {}).get("volume", 0),
        "put_vol":     c.get("put_options",  {}).get("market_data", {}).get("volume", 0),
        "call_iv":     c.get("call_options", {}).get("option_greeks", {}).get("iv", 0),
        "put_iv":      c.get("put_options",  {}).get("option_greeks", {}).get("iv", 0),
        "call_delta":  c.get("call_options", {}).get("option_greeks", {}).get("delta", 0),
        "put_delta":   c.get("put_options",  {}).get("option_greeks", {}).get("delta", 0),
        "call_gamma":  c.get("call_options", {}).get("option_greeks", {}).get("gamma", 0),
        "put_gamma":   c.get("put_options",  {}).get("option_greeks", {}).get("gamma", 0),
        "pcr":         c.get("pcr", 0),
        "underlying":  c.get("underlying_spot_price", 0),
    } for c in chain])

    if df_opt.empty:
        print(red("  ❌ Empty option chain."))
        return

    spot = df_opt["underlying"].iloc[0] if df_opt["underlying"].iloc[0] > 0 else ltp

    # ── Max Pain ──
    # Max pain = strike where total OI pain (loss to option buyers) is maximum
    max_pain_pain = {}
    strikes = sorted(df_opt["strike"].unique())
    for test_strike in strikes:
        call_pain = df_opt[df_opt["strike"] < test_strike]["call_oi"].sum() * \
                    df_opt[df_opt["strike"] < test_strike].apply(
                        lambda r: test_strike - r["strike"], axis=1).mean() if any(df_opt["strike"] < test_strike) else 0
        put_pain = df_opt[df_opt["strike"] > test_strike]["put_oi"].sum() * \
                   df_opt[df_opt["strike"] > test_strike].apply(
                       lambda r: r["strike"] - test_strike, axis=1).mean() if any(df_opt["strike"] > test_strike) else 0
        max_pain_pain[test_strike] = (call_pain or 0) + (put_pain or 0)

    max_pain_strike = min(max_pain_pain, key=max_pain_pain.get) if max_pain_pain else None

    # ── PCR ──
    total_put_oi  = df_opt["put_oi"].sum()
    total_call_oi = df_opt["call_oi"].sum()
    pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 0

    # ── Key OI Walls ──
    top_call_strikes = df_opt.nlargest(3, "call_oi")[["strike", "call_oi"]]
    top_put_strikes  = df_opt.nlargest(3, "put_oi")[["strike", "put_oi"]]

    # ── Gamma Concentration ──
    atm_strikes = df_opt[abs(df_opt["strike"] - spot) < spot * 0.03]
    gamma_exp   = (atm_strikes["call_gamma"] * atm_strikes["call_oi"] +
                   atm_strikes["put_gamma"]  * atm_strikes["put_oi"]).sum()

    print(f"\n  {'─'*60}")
    print(f"  NIFTY SPOT          : {bold(f'₹{spot:,.2f}')}")
    print(f"  {'─'*60}")
    if max_pain_strike:
        gap_pct = ((spot - max_pain_strike) / spot) * 100
        mp_signal = green(f"Spot {abs(gap_pct):.1f}% ABOVE — may drift down to max pain") if gap_pct > 0 \
                    else red(f"Spot {abs(gap_pct):.1f}% BELOW — may drift up to max pain")
        print(f"  MAX PAIN STRIKE     : {bold(magenta(f'₹{max_pain_strike:,}'))}  →  {mp_signal}")
    print(f"  PUT/CALL RATIO (PCR): {bold(f'{pcr:.2f}')}", end="  ")
    if pcr > 1.3:
        print(green("→ OVERSOLD / BULLISH CONTRARIAN (heavy puts = market floor near)"))
    elif pcr < 0.7:
        print(red("→ OVERBOUGHT / BEARISH CONTRARIAN (heavy calls = market ceiling near)"))
    else:
        print(yellow("→ NEUTRAL (balanced put/call positioning)"))
    print(f"  GAMMA EXPOSURE (ATM): {bold(f'{gamma_exp:.2f}')}", end="  ")
    if gamma_exp > 0:
        print(magenta("→ Positive gamma — MMs hedge by BUYING dips (stabilizing force)"))
    else:
        print(red("→ Negative gamma — MMs hedge by SELLING dips (destabilizing force)"))
    print(f"  {'─'*60}")

    # Resistance/Support from OI
    print(f"\n  🔴 CALL OI WALLS (Resistance / Institutional Sell Zones):")
    call_rows = [[f"₹{int(r['strike']):,}", f"{int(r['call_oi']):,}",
                  "STRONG RESISTANCE" if i == 0 else "Resistance"] for i, (_, r) in enumerate(top_call_strikes.iterrows())]
    tbl(call_rows, ["Strike", "Call OI", "Interpretation"])

    print(f"\n  🟢 PUT OI WALLS (Support / Institutional Buy Zones):")
    put_rows  = [[f"₹{int(r['strike']):,}", f"{int(r['put_oi']):,}",
                  "STRONG SUPPORT" if i == 0 else "Support"] for i, (_, r) in enumerate(top_put_strikes.iterrows())]
    tbl(put_rows, ["Strike", "Put OI", "Interpretation"])

    print(f"\n  {dim('How to read this for your stock (' + sym + '):')}")
    print(dim(f"  If NIFTY is near max pain, expect muted range. If far from max pain,"))
    print(dim(f"  directional conviction is real. OI walls act as S/R for index-linked stocks."))


# ═══════════════════════════════════════════════════════════════
#  8. PSYCHOLOGY GAUGE — FEAR, GREED, FOMO, TRAP
# ═══════════════════════════════════════════════════════════════

def analyze_psychology(df_daily, quote):
    """
    Market psychology from price action patterns.
    Detects: Panic, Euphoria, FOMO, Trap Mindset.
    """
    section("🧠 [8] MARKET PSYCHOLOGY GAUGE")

    if df_daily is None or not HAS_PANDAS:
        return

    close  = df_daily["close"]
    volume = df_daily["volume"]
    high   = df_daily["high"]
    low    = df_daily["low"]
    ltp    = quote.get("last_price") or close.iloc[-1]

    # ── Volatility (ATR) → Fear gauge ──
    atr = (high - low).tail(14).mean()
    atr_pct = (atr / ltp) * 100

    # ── Return metrics ──
    ret_1d  = ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]) * 100
    ret_5d  = ((close.iloc[-1] - close.iloc[-5]) / close.iloc[-5]) * 100
    ret_20d = ((close.iloc[-1] - close.iloc[-20]) / close.iloc[-20]) * 100

    # ── Volume trend ──
    vol_ratio = volume.tail(5).mean() / volume.tail(20).mean()

    # ── Psychology scoring ──
    print(f"\n  📐 SENTIMENT METRICS:")
    metrics = [
        ["ATR % (Volatility)",  f"{atr_pct:.2f}%",
         red("HIGH FEAR") if atr_pct > 3 else (green("CALM") if atr_pct < 1.5 else yellow("MODERATE"))],
        ["1-Day Return",        f"{ret_1d:+.2f}%",
         green("UP DAY")  if ret_1d > 1 else (red("DOWN DAY") if ret_1d < -1 else yellow("FLAT"))],
        ["5-Day Return",        f"{ret_5d:+.2f}%",
         green("SHORT BULL") if ret_5d > 5 else (red("SHORT BEAR") if ret_5d < -5 else yellow("RANGE"))],
        ["20-Day Return",       f"{ret_20d:+.2f}%",
         green("MEDIUM BULL") if ret_20d > 10 else (red("MEDIUM BEAR") if ret_20d < -10 else yellow("NEUTRAL"))],
        ["Volume vs 20D Avg",   f"{vol_ratio:.2f}x",
         green("HIGH PARTICIPATION") if vol_ratio > 1.3 else (dim("LOW PARTICIPATION") if vol_ratio < 0.7 else yellow("NORMAL"))],
    ]
    tbl(metrics, ["Metric", "Value", "Psychology Signal"])

    # ── Pattern Detection ──
    print(f"\n  🎭 BEHAVIORAL PATTERN DETECTION:")
    patterns = []

    # FOMO: fast rise + high volume + RSI extreme
    if ret_5d > 8 and vol_ratio > 1.5:
        patterns.append([red("⚠️  FOMO"), "Fast 5D rise on high vol",
                         "Retail FOMO buying — smart money may distribute into strength"])
    # Panic: fast drop + high volume
    if ret_5d < -8 and vol_ratio > 1.5:
        patterns.append([green("🔔 PANIC SELL"), "Fast 5D drop on high vol",
                         "Retail panic — potential institutional accumulation zone"])
    # Euphoria: extended run + vol dropping (topping)
    if ret_20d > 20 and vol_ratio < 0.9:
        patterns.append([red("⚠️  EUPHORIA/TOP"), "Strong 20D rally, vol declining",
                         "Smart money distributing — retail buying, institutions selling"])
    # Capitulation: extended fall + vol spike
    if ret_20d < -20 and vol_ratio > 1.5:
        patterns.append([green("🔔 CAPITULATION"), "Major 20D fall + vol spike",
                         "Final seller exhaustion — institutional accumulation likely"])
    # Trap: recent up day but weak close
    last = df_daily.iloc[-1]
    if last["close"] < last["open"] and last["high"] > last["open"] * 1.005:
        patterns.append([red("🪤 BULL TRAP"),
                         f"High ₹{last['high']:.2f} → Close ₹{last['close']:.2f}",
                         "Price rejected from highs — institutions sold into spike"])
    if last["close"] > last["open"] and last["low"] < last["open"] * 0.995:
        patterns.append([green("🪤 BEAR TRAP"),
                         f"Low ₹{last['low']:.2f} → Close ₹{last['close']:.2f}",
                         "Price recovered from lows — institutions bought the dip"])

    if not patterns:
        patterns.append([yellow("🟡 NO CLEAR PATTERN"), "Neutral conditions", "No extreme psychological state detected"])

    tbl(patterns, ["Pattern", "Evidence", "Interpretation"])

    # ── Macro warnings ──
    print(f"\n  📡 [4] MACRO CONTEXT (Indicators Cannot Know This):")
    print(f"  {dim('─'*60)}")
    print(f"  {bold('Monitor these external factors that override all signals:')}")
    macro_items = [
        ("RBI Policy Meetings",      "MPC meets 6x/year — rate changes affect all bank/NBFC stocks"),
        ("US Fed & CPI Data",        "Global risk-on/off — FII flows react before Indian markets"),
        ("India VIX",                "VIX >15 = fear, buy puts / hedge. VIX <12 = complacency, watch for spike"),
        ("Earnings Dates",           f"{bold('CHECK')} {bold(cyan('NSE calendar'))} — gaps happen overnight"),
        ("Geopolitical Events",      "Sudden reversals from news that no indicator will show"),
        ("INR/USD Rate",             "Rupee depreciation = FII outflow pressure on equities"),
        ("Nifty P/E & FII DII EOD",  "Check https://www.nseindia.com/market-data/institutional-trading daily"),
    ]
    for topic, note in macro_items:
        print(f"  {magenta('►')} {bold(topic):<30} {dim(note)}")


# ═══════════════════════════════════════════════════════════════
#  MASTER INSTITUTIONAL VIEW — SUMMARY
# ═══════════════════════════════════════════════════════════════

def print_master_view(sym, ltp, score_dict: dict):
    section("🧩 MASTER INSTITUTIONAL VIEW — ALL 8 DIMENSIONS")
    print(f"\n  Stock: {bold(cyan(sym))}  |  LTP: {bold(f'₹{ltp:,.2f}')}")
    print(f"\n  {'Dimension':<35} {'Signal':<20} {'Confidence'}")
    print(f"  {'─'*65}")
    for dim_name, (signal, confidence, note) in score_dict.items():
        print(f"  {dim_name:<35} {signal:<30} {confidence}  {dim(note)}")
    print()
    print(dim("  ⚠️  No single dimension gives the full picture."))
    print(dim("  ✅  Institutions combine ALL of the above simultaneously."))
    print(dim("  📚  Your edge = reading multiple dimensions that agree."))


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Institutional Market Intelligence Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python institutional_edge.py
  python institutional_edge.py --stock DIXON --options
        """
    )
    parser.add_argument("--stock", required=False, help=f"Stock symbol.")
    parser.add_argument("--token", default=None, help="Upstox token")
    parser.add_argument("--options", action="store_true", help="Include NIFTY options analysis")
    parser.add_argument("--no-intraday", action="store_true", help="Skip intraday candles")
    args = parser.parse_args()

    # Priority 1: Use hardcoded ACCESS_TOKEN
    token = args.token or ACCESS_TOKEN
    if not token or token == "PASTE_YOUR_UPSTOX_TOKEN_HERE":
        print(red("❌ ERROR: Set ACCESS_TOKEN at the top of the code or pass --token YOUR_TOKEN"))
        sys.exit(1)

    # Priority 2: Selection Logic
    sym = args.stock.upper() if args.stock else None
    
    if not sym:
        print(f"\n{bold(cyan('📋 YOUR INSTITUTIONAL WATCHLIST:'))}")
        stocks_list = list(WATCHLIST.keys())
        
        # Display list with numbers
        for idx, s in enumerate(stocks_list, 1):
            name_label = f"[{idx}] {s}"
            print(f"  {name_label:<18}", end="" if idx % 4 != 0 else "\n")
        
        choice = input(f"\n\n{yellow('👉 Enter Number or Stock Symbol: ')}").strip()
        
        # Check if user entered a number
        if choice.isdigit():
            idx_choice = int(choice) - 1
            if 0 <= idx_choice < len(stocks_list):
                sym = stocks_list[idx_choice]
            else:
                print(red(f"❌ Selection {choice} is out of range."))
                sys.exit(1)
        else:
            sym = choice.upper()

    if sym not in WATCHLIST:
        print(red(f"❌ '{sym}' not in watchlist. Valid: {', '.join(WATCHLIST.keys())}"))
        sys.exit(1)

    if not HAS_PANDAS:
        print(red("❌ Install pandas/numpy: pip install pandas numpy"))
        sys.exit(1)

    info = WATCHLIST[sym]

    print(DIVIDER)
    print(bold(f"  🏛️  INSTITUTIONAL EDGE — {sym} ({info['name']})"))
    print(bold(f"  {datetime.now().strftime('%d %b %Y  %H:%M:%S IST')}"))
    print(DIVIDER)

    # --- Data Fetching ---
    print(dim("\n  📡 Fetching live quote..."))
    quote = fetch_full_quote(token, info["key"])
    ltp   = quote.get("last_price", 0) or 0

    print(dim("  📡 Fetching daily candles (60 days)..."))
    df_daily = fetch_daily_candles(token, info["key"], days=60)

    df_intraday = None
    if not args.no_intraday:
        print(dim("  📡 Fetching intraday 1-min candles..."))
        df_intraday = fetch_intraday_candles(token, info["key"])
        if df_intraday is not None:
            print(dim(f"  ✅ {len(df_intraday)} intraday candles loaded"))
        else:
            print(dim("  ⚠️  Intraday data unavailable (use --no-intraday post-market)"))

    # --- Run all 8 analyses (Uses your original 900 lines of logic) ---
    analyze_dom(quote)
    analyze_order_flow(quote, df_intraday)
    analyze_institutional_positioning(df_daily, quote, sym)
    analyze_time_behavior(df_intraday)
    analyze_liquidity_zones(df_daily, df_intraday, ltp or (df_daily["close"].iloc[-1] if df_daily is not None else 0))

    if args.options:
        analyze_options(token, sym, ltp)
    else:
        print(f"\n{dim('  💡 Run with --options flag to include NIFTY options chain analysis')}")

    analyze_psychology(df_daily, quote)

    # Master summary (Using your original summary logic)
    print_master_view(sym, ltp, {
        "1. DOM (Order Book)":        (green("✅ AVAILABLE"),  "HIGH",   "5-level bid/ask depth"),
        "2. Order Flow Delta":        (yellow("⚡ PROXY"),      "MEDIUM", "Candle delta + buy/sell qty"),
        "3. Institutional Positioning":(yellow("⚡ PROXY"),     "MEDIUM", "Volume spike + price-vol divergence"),
        "4. Macro Shocks":            (red("❌ MANUAL"),        "LOW",    "Monitor RBI/Fed/VIX/news manually"),
        "5. Liquidity Engineering":   (green("✅ COMPUTED"),    "HIGH",   "Equal highs/lows, trap detection"),
        "6. Options OI & Gamma":      (green("✅ AVAILABLE") if args.options else yellow("⚡ USE --options"), "HIGH", "PCR, Max Pain, Gamma zones"),
        "7. Time-Based Behavior":      (green("✅ COMPUTED"),    "HIGH",   "Session delta from 1-min candles"),
        "8. Psychology Gauge":         (green("✅ COMPUTED"),    "MEDIUM", "ATR, vol patterns, trap detection"),
    })

    print(f"\n{DIVIDER}")
    print(dim("  ⚠️  Educational use only. Not financial advice."))
    print(DIVIDER + "\n")
if __name__ == "__main__":
    main()