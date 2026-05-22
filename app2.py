import streamlit as st
import yfinance as yf
import math
import pandas as pd
import mplfinance as mpf
import swisseph as swe
import pytz
import random
import time
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')

st.set_page_config(page_title="Astro-Gann Execution Matrix", page_icon="📈", layout="wide")

# ==========================================
# 🌌 VEDIC ASTROLOGY ENGINE CONFIGURATION
# ==========================================
swe.set_topo(72.8777, 19.0760, 14)
swe.set_sid_mode(swe.SIDM_LAHIRI)

ZODIAC_NAMES = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
ZODIAC_LORDS = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]
NAK_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"] * 3
TRANSIT_PLANETS = {swe.SUN: "Sun", swe.MOON: "Moon", swe.MERCURY: "Mercury", swe.VENUS: "Venus", swe.MARS: "Mars", swe.JUPITER: "Jupiter", swe.SATURN: "Saturn"}

FRIENDS = {"Sun": ["Moon", "Mars", "Jupiter"], "Moon": ["Sun", "Mercury"], "Mars": ["Sun", "Moon", "Jupiter"], "Mercury": ["Sun", "Venus"], "Jupiter": ["Sun", "Moon", "Mars"], "Venus": ["Mercury", "Saturn"], "Saturn": ["Mercury", "Venus"]}
ENEMIES = {"Sun": ["Venus", "Saturn"], "Moon": [], "Mars": ["Mercury"], "Mercury": ["Moon"], "Jupiter": ["Mercury", "Venus"], "Venus": ["Sun", "Moon"], "Saturn": ["Sun", "Moon", "Mars"]}

def is_pushkar(long):
    element = int(long / 30) % 4
    nav_idx = int((long % 30) / 3.333333)
    if element == 0 and nav_idx in [6, 8]: return True
    if element == 1 and nav_idx in [3, 5]: return True
    if element == 2 and nav_idx in [5, 7]: return True
    if element == 3 and nav_idx in [0, 2]: return True
    return False

def get_dignity(planet_name, lord_name):
    if planet_name == lord_name: return "🏠 Own Sign"
    if lord_name in FRIENDS.get(planet_name, []): return "🟢 Friendly"
    if lord_name in ENEMIES.get(planet_name, []): return "🔴 Enemy"
    return "⚪ Neutral"

def get_planet_data(jd, planet, pname):
    pos, _ = swe.calc_ut(jd, planet, swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_TOPOCTR)
    long, lat, speed = pos[0], pos[1], pos[3]
    d1_sign = int(long / 30)
    d9_sign = int(((long * 9) % 360) / 30)
    nak_idx = int(long / (360/27))
    return {"name": pname, "long": long, "lat": lat, "speed": speed, "d1": ZODIAC_NAMES[d1_sign], "d1_dig": get_dignity(pname, ZODIAC_LORDS[d1_sign]), "d9": ZODIAC_NAMES[d9_sign], "d9_dig": get_dignity(pname, ZODIAC_LORDS[d9_sign]), "nak": NAK_LORDS[nak_idx], "varg": "🔥 YES" if d1_sign == d9_sign else "-", "pushkar": "✨ YES" if is_pushkar(long) else "-"}

def jd_to_ist_str(jd, show_date=True):
    y, m, d, h_dec = swe.revjul(jd)
    h, min_dec = int(h_dec), (h_dec - int(h_dec)) * 60
    minute, sec = int(min_dec), int((min_dec - int(min_dec)) * 60)
    utc_dt = datetime(y, m, d, h, minute, sec, tzinfo=pytz.utc)
    ist_dt = utc_dt.astimezone(pytz.timezone('Asia/Kolkata'))
    return ist_dt.strftime("%d %b %Y, %I:%M %p") if show_date else ist_dt.strftime("%I:%M %p")

def find_exact_transit(planet, jd_start, is_d9=False, scan_days=7):
    base_pos, _ = swe.calc_ut(jd_start, planet, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)
    base_sign = int(((base_pos[0] * 9) % 360) / 30) if is_d9 else int(base_pos[0] / 30)
    
    step = 0.05
    for i in range(1, int(scan_days / step)):
        jd_f = jd_start + (i * step)
        l = swe.calc_ut(jd_f, planet, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][0]
        s = int(((l * 9) % 360) / 30) if is_d9 else int(l / 30)
        if s != base_sign:
            jd_in, jd_out = jd_f - step, jd_f
            for _ in range(15):
                mid = (jd_in + jd_out) / 2
                l_mid = swe.calc_ut(mid, planet, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][0]
                s_mid = int(((l_mid * 9) % 360) / 30) if is_d9 else int(l_mid / 30)
                if s_mid == base_sign: jd_in = mid
                else: jd_out = mid
            new_sign = int(((swe.calc_ut(jd_out + 0.01, planet, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][0] * 9) % 360) / 30) if is_d9 else int(swe.calc_ut(jd_out + 0.01, planet, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][0] / 30)
            return jd_out, ZODIAC_NAMES[new_sign]
    return None, None

def get_panchang_events(jd_start):
    events = []
    for i in range(35 * 24):
        jd_eval = jd_start + (i / 24.0)
        s_pos = swe.calc_ut(jd_eval, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][0]
        m_pos = swe.calc_ut(jd_eval, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][0]
        diff = (m_pos - s_pos) % 360
        if 0 <= diff < 0.5: events.append(("🌑 Upcoming Amavasya (New Moon)", jd_eval)); break
    for i in range(35 * 24):
        jd_eval = jd_start + (i / 24.0)
        s_pos = swe.calc_ut(jd_eval, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][0]
        m_pos = swe.calc_ut(jd_eval, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][0]
        diff = (m_pos - s_pos) % 360
        if 180 <= diff < 180.5: events.append(("🌕 Upcoming Poornima (Full Moon)", jd_eval)); break
    s_pos_start = swe.calc_ut(jd_start, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][0]
    start_sign = int(s_pos_start / 30)
    for i in range(1, 35):
        jd_eval = jd_start + i
        s_pos = swe.calc_ut(jd_eval, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SIDEREAL)[0][0]
        if int(s_pos / 30) != start_sign:
            events.append((f"🌞 Surya Sankranti (Enters {ZODIAC_NAMES[int(s_pos/30)]})", jd_eval))
            break
    return sorted(events, key=lambda x: x[1])

# ==========================================
# 📊 MARKET MATH & UTILS
# ==========================================
def degree_factor(angle): return {1: 3.75/180, 2: 7.5/180, 3: 15.00/180, 4: 18.75/180, 5: 26.25/180, 6: 45.00/180, 7: 63.75/180, 8: 71.25/180, 9: 75.00/180, 10: 82.50/180}.get(angle, 86.25/180)
def get_cycle_levels(cycle_no, prev_h, prev_l, p_range):
    df3, df6, df11 = degree_factor(3), degree_factor(6), degree_factor(11)
    sqrt_pr = math.sqrt(p_range)
    if cycle_no == 1: return [((sqrt_pr + df3)**2) * df3 + prev_h, ((sqrt_pr + df6)**2) * df6 + prev_h, ((sqrt_pr + df11)**2) * df11 + prev_h, prev_h - ((sqrt_pr - df3)**2) * df3, prev_h - ((sqrt_pr - df6)**2) * df6, prev_h - ((sqrt_pr - df11)**2) * df11]
    else: return [((sqrt_pr + df6)**2) * df6 + prev_h, ((sqrt_pr + df11)**2) * df11 + prev_h, prev_l - ((sqrt_pr - df6)**2) * df6, prev_l - ((sqrt_pr - df11)**2) * df11, 0.0, 0.0]

def calculate_atr(df, period=14): return pd.concat([df['High'] - df['Low'], (df['High'] - df['Close'].shift()).abs(), (df['Low'] - df['Close'].shift()).abs()], axis=1).max(axis=1).rolling(window=period).mean().iloc[-1]
def calculate_rsi(series, period=14):
    delta = series.diff()
    rs = (delta.where(delta > 0, 0)).fillna(0).rolling(window=period, min_periods=1).mean() / (-delta.where(delta < 0, 0)).fillna(0).rolling(window=period, min_periods=1).mean()
    return 100 - (100 / (1 + rs))

@st.cache_data(ttl=300) 
def fetch_market_data(ticker, date_str, period_d, interval_i):
    return yf.Ticker(ticker).history(end=date_str, period=period_d, interval=interval_i)

TOP_100_INDIA = [
    ("RELIANCE", "RELIANCE.NS"), ("HDFC BANK", "HDFCBANK.NS"), ("TCS", "TCS.NS"), 
    ("INFOSYS", "INFY.NS"), ("ICICI BANK", "ICICIBANK.NS"), ("BHARTI AIRTEL", "BHARTIARTL.NS"), 
    ("STATE BANK OF INDIA", "SBIN.NS"), ("ITC", "ITC.NS"), ("LARSEN & TOUBRO", "LT.NS"), 
    ("HINDUSTAN UNILEVER", "HINDUNILVR.NS"), ("BAJAJ FINANCE", "BAJAJFINSV.NS"), ("HCL TECH", "HCLTECH.NS"),
    ("MARUTI SUZUKI", "MARUTI.NS"), ("SUN PHARMA", "SUNPHARMA.NS"), ("TATA MOTORS", "TATAMOTORS.NS"),
    ("AXIS BANK", "AXISBANK.NS"), ("ADANI ENTERPRISES", "ADANIENT.NS"), ("NTPC", "NTPC.NS"),
    ("KOTAK MAHINDRA BANK", "KOTAKBANK.NS"), ("TITAN COMPANY", "TITAN.NS"), ("COAL INDIA", "COALINDIA.NS"),
    ("TATA STEEL", "TATASTEEL.NS"), ("ULTRATECH CEMENT", "ULTRACEMCO.NS"), ("ASIAN PAINTS", "ASIANPAINT.NS"),
    ("POWER GRID", "POWERGRID.NS"), ("MAHINDRA & MAHINDRA", "M&M.NS"), ("JIO FINANCIAL", "JIOFIN.NS"),
    ("BAJAJ AUTO", "BAJAJ-AUTO.NS"), ("JSW STEEL", "JSWSTEEL.NS"), ("ADANI PORTS", "ADANIPORTS.NS"),
    ("INDUSIND BANK", "INDUSINDBK.NS"), ("HINDALCO", "HINDALCO.NS"), ("BPCL", "BPCL.NS"),
    ("NESTLE INDIA", "NESTLEIND.NS"), ("GRASIM", "GRASIM.NS"), ("DR REDDY", "DRREDDY.NS"),
    ("TECH MAHINDRA", "TECHM.NS"), ("CIPLA", "CIPLA.NS"), ("EICHER MOTORS", "EICHERMOT.NS"),
    ("WIPRO", "WIPRO.NS"), ("BRITANNIA", "BRITANNIA.NS"), ("APOLLO HOSPITALS", "APOLLOHOSP.NS"),
    ("SHREE CEMENT", "SHREECEM.NS"), ("DIVIS LAB", "DIVISLAB.NS"), ("BAJAJ FINSERV", "BAJAJFINSV.NS"),
    ("SBI LIFE", "SBILIFE.NS"), ("HERO MOTOCORP", "HEROMOTOCO.NS"), ("LTIMINDTREE", "LTIM.NS"),
    ("TATA CONSUMER", "TATACONSUM.NS"), ("ONGC", "ONGC.NS"), ("ADANI GREEN", "ADANIGREEN.NS"),
    ("DLF", "DLF.NS"), ("ZOMATO", "ZOMATO.NS"), ("HAL", "HAL.NS"), ("BEL", "BEL.NS"),
    ("VBL", "VBL.NS"), ("TRENT", "TRENT.NS"), ("IRFC", "IRFC.NS"), ("REC LTD", "RECLTD.NS"),
    ("PFC", "PFC.NS"), ("GAIL", "GAIL.NS"), ("ABB INDIA", "ABB.NS"), ("SIEMENS", "SIEMENS.NS"),
    ("AMBUJA CEMENT", "AMBUJACEM.NS"), ("PNB", "PNB.NS"), ("BOB", "BANKBARODA.NS"),
    ("HAVELLS", "HAVELLS.NS"), ("PIDILITE", "PIDILITIND.NS"), ("ICICI PRUDENTIAL", "ICICIPRULI.NS"),
    ("ICICI LOMBARD", "ICICIGI.NS"), ("MARICO", "MARICO.NS"), ("SRF", "SRF.NS"),
    ("MUTHOOT FINANCE", "MUTHOOTFIN.NS"), ("GODREJ PROPERTIES", "GODREJPROP.NS"), ("CHOLAMANDALAM", "CHOLAFIN.NS"),
    ("OBEROI REALTY", "OBEROIRLTY.NS"), ("AU SMALL FINANCE", "AUBANK.NS"), ("COLGATE", "COLPAL.NS"),
    ("LUPIN", "LUPIN.NS"), ("BIOCON", "BIOCON.NS"), ("BANDHAN BANK", "BANDHANBNK.NS"),
    ("JUBLFOOD", "JUBLFOOD.NS"), ("NMDC", "NMDC.NS"), ("SAIL", "SAIL.NS"), ("PAGE INDUSTRIES", "PAGEIND.NS"),
    ("UPL", "UPL.NS"), ("POLYCAB", "POLYCAB.NS"), ("MAX HEALTHCARE", "MAXHEALTH.NS"),
    ("PERSISTENT SYSTEMS", "PERSISTENT.NS"), ("MPHASIS", "MPHASIS.NS"), ("DIXON", "DIXON.NS"),
    ("COFORGE", "COFORGE.NS"), ("BERGER PAINTS", "BERGEPAINT.NS"), ("TATA COMMUNICATIONS", "TATACOMM.NS"),
    ("ASHOK LEYLAND", "ASHOKLEY.NS"), ("MRF", "MRF.NS"), ("BALKRISHNA IND", "BALKRISIND.NS"),
    ("TATA POWER", "TATAPOWER.NS"), ("VOLTAS", "VOLTAS.NS"), ("PETRONET LNG", "PETRONET.NS")
]
GLOBAL_INDICES = [("NIFTY 50 (India)", "^NSEI"), ("BANK NIFTY (India)", "^NSEBANK"), ("S&P 500 (USA)", "^GSPC")]

# ==========================================
# 🖥️ UI & SIDEBAR PARAMS
# ==========================================
st.sidebar.header("🎯 Target Parameters")
asset_type = st.sidebar.radio("Asset Category Selector", ["Global Index", "India Top 100 Stocks", "Custom Ticker / Crypto Symbol"])

if asset_type == "Global Index":
    idx_choice = st.sidebar.selectbox("Choose Index", GLOBAL_INDICES, format_func=lambda x: x[0])
    display_name, ticker_symbol = idx_choice[0], idx_choice[1]
elif asset_type == "India Top 100 Stocks":
    stock_choice = st.sidebar.selectbox("Choose Popular Stock", TOP_100_INDIA, format_func=lambda x: f"{x[0]} ({x[1]})")
    display_name, ticker_symbol = stock_choice[0], stock_choice[1]
else:
    custom_input = st.sidebar.text_input("Enter Ticker Symbol", "^NSEI").strip()
    ticker_symbol, display_name = custom_input, custom_input.upper()

interval_used = st.sidebar.radio("Select Candlestick Timeframe", ["5m", "15m", "30m", "1h"])
trader_type = st.sidebar.radio("Options Trading Style", ["Option Buyer (CE/PE Buy)", "Option Seller (CE/PE Write)"])
target_date = st.sidebar.date_input("Execution Date", datetime.now().date())
target_dt = datetime(target_date.year, target_date.month, target_date.day)

open_price_type = st.sidebar.radio("Opening Price Type", ["Auto-Fetch Previous Close", "Manual Override Price"])
manual_open_val = st.sidebar.number_input("Enter Manual Price", value=0.0, step=0.05) if open_price_type == "Manual Override Price" else 0.0
  st.title(f"📈 Gann Execution Matrix: {display_name}")

with st.spinner(f"Compiling High-Precision Mathematical Targets for {display_name}..."):
    try:
        target_date_str = target_dt.strftime("%Y-%m-%d")
        df_daily = fetch_market_data(ticker_symbol, target_date_str, "60d", "1d")
        hist_period = "5d" if interval_used in ["5m", "15m"] else "10d" if interval_used == "30m" else "20d"
        df_intra = fetch_market_data(ticker_symbol, target_date_str, hist_period, interval_used)
        
        if df_daily.empty or df_intra.empty:
            st.error(f"❌ Waiting for valid data for {ticker_symbol}. Ensure the ticker is correct.")
            st.stop()
            
        df_daily.index, df_intra.index = df_daily.index.tz_localize(None), df_intra.index.tz_localize(None)
        
        # --- TECHNICAL METRICS & GAP LOGIC ---
        pdh, pdl, pdc = df_daily['High'].iloc[-2] if len(df_daily) > 1 else df_daily['High'].iloc[-1], df_daily['Low'].iloc[-2] if len(df_daily) > 1 else df_daily['Low'].iloc[-1], df_daily['Close'].iloc[-2] if len(df_daily) > 1 else df_daily['Close'].iloc[-1]
        
        OPEN_PRICE = manual_open_val if open_price_type == "Manual Override Price" and manual_open_val != 0.0 else df_daily['Close'].iloc[-1]
        
        gap_pts = OPEN_PRICE - pdc
        gap_pct = (gap_pts / pdc) * 100 if pdc != 0 else 0
        gap_status = f"🟢 GAP UP ({gap_pct:+.2f}%)" if gap_pts > (pdc * 0.001) else f"🔴 GAP DOWN ({gap_pct:+.2f}%)" if gap_pts < -(pdc * 0.001) else f"⚪ FLAT OPEN ({gap_pct:+.2f}%)"
        
        # Determine anchor price
        closes = df_daily['Close'].iloc[-10:].values[::-1]
        c1 = OPEN_PRICE if (OPEN_PRICE > pdh or OPEN_PRICE < pdl) else closes[0]
        anchor_desc = "Today's Open (Gap Outside Range)" if c1 == OPEN_PRICE else "Yesterday's Close (Inside Range)"

        # --- MACRO TREND (Daily) ---
        df_daily['EMA9'], df_daily['EMA21'], df_daily['EMA50'] = df_daily['Close'].ewm(span=9).mean(), df_daily['Close'].ewm(span=21).mean(), df_daily['Close'].ewm(span=50).mean()
        c, e9, e21, e50 = df_daily['Close'].iloc[-1], df_daily['EMA9'].iloc[-1], df_daily['EMA21'].iloc[-1], df_daily['EMA50'].iloc[-1]
        w1_view = "📈 BULLISH" if c > e9 else "📉 BEARISH"
        w2_view = "📈 BULLISH" if c > e21 and e9 > e21 else "📉 BEARISH" if c < e21 else "⏳ SIDEWAYS"
        m1_view = "📈 STRONG BULL" if c > e50 and e21 > e50 else "📉 STRONG BEAR" if c < e50 and e21 < e50 else "⏳ CONSOLIDATING"

        # --- MICRO TREND (Intraday Momentum to catch reversals) ---
        df_intra['EMA9'], df_intra['EMA21'] = df_intra['Close'].ewm(span=9).mean(), df_intra['Close'].ewm(span=21).mean()
        df_intra['RSI'] = calculate_rsi(df_intra['Close'])
        ic, ie9, ie21, irsi = df_intra['Close'].iloc[-1], df_intra['EMA9'].iloc[-1], df_intra['EMA21'].iloc[-1], df_intra['RSI'].iloc[-1]
        
        # Incorporate Gap Up into early morning intraday trend
        if gap_pts > (pdc * 0.003) and ic > ie21: day_trend = "🚀 STRONG BULLISH (Gap Up Sustained)"
        elif gap_pts < -(pdc * 0.003) and ic < ie21: day_trend = "🩸 STRONG BEARISH (Gap Down Sustained)"
        elif ic > ie9 > ie21 and irsi > 50: day_trend = "📈 BULLISH (Momentum Up)"
        elif ic < ie9 < ie21 and irsi < 50: day_trend = "📉 BEARISH (Momentum Down)"
        else: day_trend = "⏳ SIDEWAYS / REVERSING"

        # --- BTST / STBT LOGIC ---
        pd_vwap = (df_daily['High'].iloc[-1] + df_daily['Low'].iloc[-1] + df_daily['Close'].iloc[-1]) / 3
        btst_rec = "Neutral / No Trade"
        if ic > pd_vwap and ic > ie9 and irsi > 55: btst_rec = "🟢 BTST (Buy Call / Carry Long) - Sustaining above VWAP"
        elif ic < pd_vwap and ic < ie9 and irsi < 45: btst_rec = "🔴 STBT (Buy Put / Carry Short) - Bleeding below VWAP"

        # --- GANN TARGET MATH ---
        atr_14 = calculate_atr(df_daily, period=14)
        log_returns = [math.log((c1 if i == 0 else closes[i]) / closes[i+1]) for i in range(9)]
        price_range = math.sqrt(max((sum([r**2 for r in log_returns]) / 9) - ((sum(log_returns) / 9) ** 2), 0.0001)) * c1
        
        levels = [get_cycle_levels(1, c1, 0.0, price_range)]
        prev_b, prev_s = levels[0][2], levels[0][5]
        for cycle in range(2, 6):
            c_levels = get_cycle_levels(cycle, prev_b, prev_s, price_range)
            levels.append(c_levels)
            prev_b, prev_s = c_levels[1], c_levels[3]
        b_above, res, t1_b, s_below, sup, t1_s = levels[0]

        # --- OPTIONS SELECTION ---
        strike_step = 50 if "^NSEI" in ticker_symbol else (100 if "BANK" in ticker_symbol else max(1, round(pdc * 0.01)))
        atm_strike = round(OPEN_PRICE / strike_step) * strike_step
        opt_rec, est_return = "", ""
        if "Buyer" in trader_type:
            if "BULL" in day_trend: opt_rec = f"Buy `{atm_strike} CE` or `{atm_strike - strike_step} CE`"
            elif "BEAR" in day_trend: opt_rec = f"Buy `{atm_strike} PE` or `{atm_strike + strike_step} PE`"
            else: opt_rec = "Hold / Wait for Trend confirmation"
            est_return = f"{int((abs(t1_b - OPEN_PRICE) * 0.5) / atr_14 * 100)}% - {int((abs(levels[1][1] - OPEN_PRICE) * 0.5) / atr_14 * 100)}% (Tentative)"
        else:
            if "BULL" in day_trend: opt_rec = f"Write/Sell `{atm_strike - strike_step*2} PE`"
            elif "BEAR" in day_trend: opt_rec = f"Write/Sell `{atm_strike + strike_step*2} CE`"
            else: opt_rec = f"Short Strangle/Straddle near `{atm_strike}`"
            est_return = "Max Premium Decay (Theta)"

        avg_candle_pts = abs(df_intra['High'].iloc[-15:].mean() - df_intra['Low'].iloc[-15:].mean())
        mins_per_candle = int(interval_used.replace('m','').replace('h','60'))
        def est_time(target_pts):
            candles = max(1, target_pts / max(1, avg_candle_pts))
            return (datetime(target_dt.year, target_dt.month, target_dt.day, 9, 15) + timedelta(minutes=candles * mins_per_candle)).strftime("%I:%M %p")

        # ---------------------------------------------------------
        # SECTION 1: TRADING SIGNALS & TECHNICALS
        # ---------------------------------------------------------
        st.subheader("⚙️ Technical & Price Action Blueprint")
        tech_df = pd.DataFrame({"Metric": ["Used Anchor Price", "Gap Analysis", "Current Intraday Trend", "Current Intraday RSI", "BTST / STBT Verdict"], "Value": [f"{OPEN_PRICE:,.2f} ({anchor_desc})", gap_status, day_trend, f"{irsi:.2f}", btst_rec]})
        st.table(tech_df)

        col_lt, col_opt = st.columns(2)
        with col_lt:
            st.subheader("🔭 Macro Forecasting Matrix")
            st.table(pd.DataFrame({"Timeframe": ["1 Week Out", "2 Weeks Out", "1 Month Out"], "Forecast": [w1_view, w2_view, m1_view]}))
        with col_opt:
            st.subheader("🎯 Options Execution Plan")
            st.info(f"**Action:** {opt_rec}  \n**Est. Return ROI:** {est_return}")

        st.subheader("📐 High-Precision Mathematical Targets")
        g1, g2 = st.columns(2)
        with g1:
            st.success(f"🟢 LONG TRADING SETUP (CE)")
            st.write(f"**Trigger Above:** `{b_above:,.2f}`")
            st.write(f"**Target 1:** `{t1_b:,.2f}` ⏳ Hit Time: ~`{est_time(abs(t1_b - OPEN_PRICE))}`")
            st.write(f"**Target 2:** `{levels[1][1]:,.2f}` ⏳ Hit Time: ~`{est_time(abs(levels[1][1] - OPEN_PRICE))}`")
            st.write(f"**Target 3:** `{levels[2][1]:,.2f}` ⏳ Hit Time: ~`{est_time(abs(levels[2][1] - OPEN_PRICE))}`")
        with g2:
            st.error(f"🔴 SHORT TRADING SETUP (PE)")
            st.write(f"**Trigger Below:** `{s_below:,.2f}`")
            st.write(f"**Target 1:** `{t1_s:,.2f}` ⏳ Hit Time: ~`{est_time(abs(t1_s - OPEN_PRICE))}`")
            st.write(f"**Target 2:** `{levels[1][3]:,.2f}` ⏳ Hit Time: ~`{est_time(abs(levels[1][3] - OPEN_PRICE))}`")
            st.write(f"**Target 3:** `{levels[2][3]:,.2f}` ⏳ Hit Time: ~`{est_time(abs(levels[2][3] - OPEN_PRICE))}`")

        st.subheader("📈 Visual Chart Mapping")
        apds = [mpf.make_addplot(df_intra['EMA9'].tail(75), color='#1f77b4', width=1.2), mpf.make_addplot(df_intra['EMA21'].tail(75), color='#ff7f0e', width=1.2), mpf.make_addplot(df_intra['RSI'].tail(75), panel=2, color='#b284be', ylabel='RSI')]
        h_lines = [float(b_above), float(s_below), float(t1_b), float(t1_s)]
        c_lines = ['#00ff00', '#ff0000', '#00b300', '#cc0000']
        fig, _ = mpf.plot(df_intra.tail(75), type='candle', style='nightclouds', figsize=(15, 6), addplot=apds, volume=True, panel_ratios=(5,1,1), hlines=dict(hlines=h_lines, colors=c_lines, linestyle='-'), returnfig=True)
        st.pyplot(fig)

        # ---------------------------------------------------------
        # SECTION 2: ASTROLOGY ENGINE
        # ---------------------------------------------------------
        st.write("---")
        st.header("🌌 Financial Astrology Matrix (Timing & Dignities)")
        
        ist = pytz.timezone('Asia/Kolkata')
        market_open = ist.localize(datetime(target_dt.year, target_dt.month, target_dt.day, 9, 15))
        jd_open = swe.julday(market_open.year, market_open.month, market_open.day, market_open.hour + market_open.minute/60.0 - 5.5)

        planets_data = [get_planet_data(jd_open, pid, pname) for pid, pname in TRANSIT_PLANETS.items()]
        
        st.subheader("🪐 Current Day Dignities & Conjunctions")
        astro_df = pd.DataFrame(planets_data)[["name", "d1", "d1_dig", "d9", "d9_dig", "nak", "varg", "pushkar"]]
        astro_df.columns = ["Planet", "D1 Sign", "D1 Dignity", "D9 Sign", "D9 Dignity", "Nakshatra", "Vargottam", "Pushkar"]
        st.table(astro_df)

        d1_map = {}
        for p in planets_data: d1_map.setdefault(p['d1'], []).append(p['name'])
        conjunctions = {s: p_list for s, p_list in d1_map.items() if len(p_list) > 1}
        if conjunctions:
            st.info("**Active D1 Conjunctions:** " + " | ".join([f"{s}: {' + '.join(pls)}" for s, pls in conjunctions.items()]))

        st.subheader("☀️🌙 Special Focus: Sun & Moon Upcoming Ingress")
        sm_col1, sm_col2 = st.columns(2)
        with sm_col1:
            jd_d1, s_d1 = find_exact_transit(swe.SUN, jd_open, False, 35)
            jd_d9, s_d9 = find_exact_transit(swe.SUN, jd_open, True, 7)
            if jd_d1: st.markdown(f"**☀️ SUN D1 Sign Change:** Enters `{s_d1}` on `{jd_to_ist_str(jd_d1)}`")
            else: st.markdown("**☀️ SUN D1:** No change in 30 days.")
            if jd_d9: st.markdown(f"**☀️ SUN D9 Sign Change:** Enters `{s_d9}` on `{jd_to_ist_str(jd_d9)}`")
            else: st.markdown("**☀️ SUN D9:** No change in 7 days.")
                
        with sm_col2:
            jd_m_d1, m_d1 = find_exact_transit(swe.MOON, jd_open, False, 3)
            jd_m_d9, m_d9 = find_exact_transit(swe.MOON, jd_open, True, 1)
            if jd_m_d1: st.markdown(f"**🌙 MOON D1 Sign Change:** Enters `{m_d1}` on `{jd_to_ist_str(jd_m_d1)}`")
            else: st.markdown("**🌙 MOON D1:** No change in 3 days.")
            if jd_m_d9: st.markdown(f"**🌙 MOON D9 Sign Change:** Enters `{m_d9}` on `{jd_to_ist_str(jd_m_d9)}`")
            else: st.markdown("**🌙 MOON D9:** No change today.")

        st.subheader("🔭 Upcoming Weekly Transits (D1 & D9)")
        weekly_transits = []
        for pid, pname in {swe.MERCURY: "Mercury", swe.VENUS: "Venus", swe.MARS: "Mars", swe.JUPITER: "Jupiter", swe.SATURN: "Saturn"}.items():
            jd_d1, sign_d1 = find_exact_transit(pid, jd_open, False, 14)
            if jd_d1: weekly_transits.append(f"• **{pname} D1** enters **{sign_d1}** on `{jd_to_ist_str(jd_d1)}`")
            jd_d9, sign_d9 = find_exact_transit(pid, jd_open, True, 7)
            if jd_d9: weekly_transits.append(f"• **{pname} D9** enters **{sign_d9}** on `{jd_to_ist_str(jd_d9)}`")
        
        if weekly_transits:
            for t in sorted(weekly_transits): st.write(t)
        else:
            st.write("No major planetary sign changes in the upcoming week.")

        st.write("---")
        st.subheader("🕉️ Important Vedic Events (Panchang)")
        panchang_events = get_panchang_events(jd_open)
        for ev, jd in panchang_events:
            st.write(f"**{ev}**: Exact timing at `{jd_to_ist_str(jd)}`")

    except Exception as e:
        st.error(f"❌ Execution Engine Error: {str(e)}. Please check inputs.")
                              
