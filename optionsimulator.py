import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime

# --- UI Setup ---
st.title("Nifty 0.5 Delta Options Simulator")
st.sidebar.header("Strategy Parameters")

capital = st.sidebar.number_input("Capital (₹)", value=15000, step=5000)
lot_size = st.sidebar.number_input("Lot Size", value=65, step=1)
premium = st.sidebar.number_input("ATM Premium (₹)", value=150, step=10)
target_pct = st.sidebar.slider("Target %", 1, 50, 10)
sl_pct = st.sidebar.slider("Stop Loss %", 1, 50, 20)
slippage_pct = st.sidebar.slider("Slippage %", 0.0, 2.0, 0.2, step=0.1)

# Math breakdown
lots_tradable = capital // (lot_size * premium)
option_target_pts = premium * (target_pct / 100)
option_sl_pts = premium * (sl_pct / 100)
nifty_target_req = option_target_pts * 2  # 0.5 Delta rule
nifty_sl_req = option_sl_pts * 2

st.sidebar.markdown(f"**Max Lots:** {lots_tradable}")
st.sidebar.markdown(f"**Nifty Pts needed for Target:** {nifty_target_req}")
st.sidebar.markdown(f"**Nifty Pts needed for SL:** {nifty_sl_req}")

# --- Data Handling (Past, Present, Future) ---
st.subheader("1. Load Market Data")
data_source = st.radio("Select Data Source:", ["Fetch Today/Recent (yfinance)", "Upload Historical CSV"])

df = None
if data_source == "Fetch Today/Recent (yfinance)":
    # yfinance ticker for Nifty 50 is ^NSEI
    period = st.selectbox("Select Timeframe", ["1d", "5d", "1mo"])
    if st.button("Fetch Nifty Data"):
        df = yf.download("^NSEI", period=period, interval="1m")
        df.reset_index(inplace=True)
        # Handle yfinance timezone formats
        df['Time'] = pd.to_datetime(df['Datetime']).dt.strftime('%H:%M')
        st.success(f"Fetched {len(df)} rows of data.")

elif data_source == "Upload Historical CSV":
    uploaded_file = st.file_uploader("Upload 1-Min Nifty Data CSV", type=["csv"])
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        st.success("CSV Loaded successfully. Ensure it has a 'Time' and 'Close' column.")

# --- Simulator Logic ---
if df is not None and not df.empty:
    st.subheader("2. Input Your Signals")
    
    # Example signals based on your strategy
    default_signals = pd.DataFrame([
        {"Time": "09:21", "Action": "REVERSAL (LONG)"},
        {"Time": "09:56", "Action": "SHORT"},
        {"Time": "10:28", "Action": "LONG"},
        {"Time": "12:38", "Action": "SHORT"},
        {"Time": "14:23", "Action": "LONG"},
        {"Time": "14:45", "Action": "LONG"}
    ])
    
    edited_signals = st.data_editor(default_signals, num_rows="dynamic")
    
    if st.button("Run Simulation"):
        results = []
        total_pnl = 0
        total_slippage = 0
        
        for index, row in edited_signals.iterrows():
            signal_time = row['Time']
            action = row['Action']
            
            # Find the index of the signal time in the dataframe
            entry_data = df[df['Time'] >= signal_time]
            
            if entry_data.empty:
                continue
                
            entry_price = entry_data.iloc[0]['Close']
            outcome = "Time Ran Out"
            points_captured = 0
            
            # Scan forward minute-by-minute from entry
            for _, minute_data in entry_data.iterrows():
                current_price = minute_data['Close']
                
                if "LONG" in action.upper():
                    move = current_price - entry_price
                    if move >= nifty_target_req:
                        outcome = "Target Hit"
                        points_captured = option_target_pts
                        break
                    elif move <= -nifty_sl_req:
                        outcome = "Stop Loss Hit"
                        points_captured = -option_sl_pts
                        break
                        
                elif "SHORT" in action.upper():
                    move = entry_price - current_price
                    if move >= nifty_target_req:
                        outcome = "Target Hit"
                        points_captured = option_target_pts
                        break
                    elif move <= -nifty_sl_req:
                        outcome = "Stop Loss Hit"
                        points_captured = -option_sl_pts
                        break
            
            # Math
            gross_pnl = points_captured * lot_size * lots_tradable
            trade_turnover = (premium * lot_size * lots_tradable) * 2 # Buy and Sell
            slippage_cost = trade_turnover * (slippage_pct / 100)
            net_pnl = gross_pnl - slippage_cost - 40 # Assuming flat 40 rs brokerage per trade
            
            total_pnl += net_pnl
            total_slippage += slippage_cost
            
            results.append({
                "Time": signal_time,
                "Action": action,
                "Entry Price": round(entry_price, 2),
                "Outcome": outcome,
                "Net PnL (₹)": round(net_pnl, 2)
            })
            
        st.subheader("3. Simulation Results")
        st.table(pd.DataFrame(results))
        
        st.metric(label="Total Net PnL (After Slippage & Brokerage)", value=f"₹ {round(total_pnl, 2)}")
        st.metric(label="Total Wealth Lost to Slippage", value=f"₹ {round(total_slippage, 2)}")
