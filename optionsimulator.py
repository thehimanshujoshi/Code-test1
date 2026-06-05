import streamlit as st
import pandas as pd
import yfinance as yf

# --- UI Setup ---
st.set_page_config(page_title="Nifty Simulator", layout="wide")
st.title("Nifty 0.5 Delta Options Simulator (with Trailing SL)")
st.sidebar.header("Strategy Parameters")

capital = st.sidebar.number_input("Capital (Base Currency)", value=15000, step=5000)
lot_size = st.sidebar.number_input("Lot Size", value=65, step=1)
premium = st.sidebar.number_input("ATM Premium", value=150, step=10)
target_pct = st.sidebar.slider("Target % (Set high if using Trailing SL)", 1, 200, 10)
sl_pct = st.sidebar.slider("Initial Stop Loss %", 1, 50, 20)
slippage_pct = st.sidebar.slider("Slippage %", 0.0, 2.0, 0.2, step=0.1)

# Trailing Stop Loss Controls
st.sidebar.subheader("Trailing SL Settings")
use_trailing = st.sidebar.checkbox("Enable Trailing Stop Loss", value=True)

# Math breakdown
lots_tradable = capital // (lot_size * premium)
option_target_pts = premium * (target_pct / 100)
option_sl_pts = premium * (sl_pct / 100)

nifty_target_req = option_target_pts * 2  # 0.5 Delta rule
nifty_sl_req = option_sl_pts * 2          # 0.5 Delta rule

st.sidebar.markdown(f"**Max Lots Afforded:** {lots_tradable}")
st.sidebar.markdown(f"**Initial SL Buffer (Nifty Pts):** {nifty_sl_req}")

# --- Data Handling ---
st.subheader("1. Load Market Data")
data_source = st.radio("Select Data Source:", ["Fetch Today/Recent (yfinance)", "Upload Historical CSV"])

df = None
if data_source == "Fetch Today/Recent (yfinance)":
    period = st.selectbox("Select Timeframe", ["1d", "5d", "1mo"])
    if st.button("Fetch Nifty Data"):
        df = yf.download("^NSEI", period=period, interval="1m")
        df.reset_index(inplace=True)
        df['Time'] = pd.to_datetime(df['Datetime']).dt.strftime('%H:%M')
        st.success(f"Fetched {len(df)} rows of data.")

elif data_source == "Upload Historical CSV":
    uploaded_file = st.file_uploader("Upload 1-Min Nifty Data CSV", type=["csv"])
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        st.success("CSV Loaded successfully.")

# --- Simulator Logic ---
if df is not None and not df.empty:
    st.subheader("2. Input Your Signals")
    
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
            
            entry_data = df[df['Time'] >= signal_time]
            if entry_data.empty:
                continue
                
            entry_price = entry_data.iloc[0]['Close']
            outcome = "Time Ran Out"
            points_captured = 0
            
            # Trailing tracking variables
            max_favorable_move = 0 
            
            for _, minute_data in entry_data.iterrows():
                current_price = minute_data['Close']
                
                if "LONG" in action.upper():
                    current_move = current_price - entry_price
                    
                    if use_trailing:
                        # Track the highest Nifty spot reached since entry
                        max_favorable_move = max(max_favorable_move, current_move)
                        # Dynamic trailing stop loss line
                        current_sl_line = max_favorable_move - nifty_sl_req
                        
                        if current_move >= nifty_target_req:
                            outcome = "Target Hit"
                            points_captured = option_target_pts
                            break
                        elif current_move <= current_sl_line:
                            outcome = "Trailing SL Hit" if max_favorable_move > 0 else "Initial SL Hit"
                            # Option points captured is half of the Nifty move at exit
                            points_captured = current_sl_line / 2
                            break
                    else:
                        # Standard Fixed Target / SL
                        if current_move >= nifty_target_req:
                            outcome = "Target Hit"
                            points_captured = option_target_pts
                            break
                        elif current_move <= -nifty_sl_req:
                            outcome = "Stop Loss Hit"
                            points_captured = -option_sl_pts
                            break
                        
                elif "SHORT" in action.upper():
                    current_move = entry_price - current_price
                    
                    if use_trailing:
                        # Track the lowest Nifty spot reached since entry
                        max_favorable_move = max(max_favorable_move, current_move)
                        current_sl_line = max_favorable_move - nifty_sl_req
                        
                        if current_move >= nifty_target_req:
                            outcome = "Target Hit"
                            points_captured = option_target_pts
                            break
                        elif current_move <= current_sl_line:
                            outcome = "Trailing SL Hit" if max_favorable_move > 0 else "Initial SL Hit"
                            points_captured = current_sl_line / 2
                            break
                    else:
                        if current_move >= nifty_target_req:
                            outcome = "Target Hit"
                            points_captured = option_target_pts
                            break
                        elif current_move <= -nifty_sl_req:
                            outcome = "Stop Loss Hit"
                            points_captured = -option_sl_pts
                            break
            
            # Financial calculations
            gross_pnl = points_captured * lot_size * lots_tradable
            trade_turnover = (premium * lot_size * lots_tradable) * 2
            slippage_cost = trade_turnover * (slippage_pct / 100)
            net_pnl = gross_pnl - slippage_cost - 40  # Flat flat ₹40 brokerage
            
            total_pnl += net_pnl
            total_slippage += slippage_cost
            
            results.append({
                "Time": signal_time,
                "Action": action,
                "Entry Price": round(entry_price, 2),
                "Outcome": outcome,
                "Points Captured (Opt)": round(points_captured, 1),
                "Net PnL": round(net_pnl, 2)
            })
            
        # Display Dashboard Metrics
        st.subheader("3. Simulation Results")
        st.dataframe(pd.DataFrame(results), use_container_width=True)
        
        col1, col2 = st.columns(2)
        col1.metric(label="Total Strategy Net PnL", value=f"₹ {round(total_pnl, 2)}")
        col2.metric(label="Slippage Friction Loss", value=f"₹ {round(total_slippage, 2)}")
