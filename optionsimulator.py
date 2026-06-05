import streamlit as st
import pandas as pd
import yfinance as yf

# --- Initialize Session State ---
# This prevents the app from "forgetting" the data when you click the run button
if 'market_data' not in st.session_state:
    st.session_state['market_data'] = None

# --- UI Setup ---
st.set_page_config(page_title="Universal Options Simulator", layout="wide")
st.title("Universal Options Strategy Simulator")

# --- Strategy Parameters (Sidebar) ---
st.sidebar.header("1. Asset Profile")
ticker = st.sidebar.text_input("Ticker Symbol (Default: Nifty 50)", value="^NSEI")
base_lot_size = st.sidebar.number_input("Base Lot Size (e.g., 65 for Nifty)", value=65, step=1)

# The total quantity automatically forces you into multiples of the base lot size
total_qty = st.sidebar.number_input(
    "Total Trading Quantity", 
    min_value=base_lot_size, 
    value=base_lot_size, 
    step=base_lot_size
)

option_delta = st.sidebar.number_input("Option Delta (e.g., 0.5 for ATM)", value=0.5, step=0.1)
premium = st.sidebar.number_input("Average Premium Paid (₹)", value=150, step=10)

st.sidebar.header("2. Risk Management")
target_pct = st.sidebar.slider("Target Profit %", 1, 200, 10)
sl_pct = st.sidebar.slider("Stop Loss %", 1, 50, 20)
use_trailing = st.sidebar.checkbox("Enable Trailing Stop Loss", value=True)
slippage_pct = st.sidebar.slider("Slippage %", 0.0, 2.0, 0.2, step=0.1)

# --- Math Breakdown ---
# Calculate the required point movements on the underlying asset using the Delta
option_target_pts = premium * (target_pct / 100)
option_sl_pts = premium * (sl_pct / 100)

underlying_target_req = option_target_pts / option_delta  
underlying_sl_req = option_sl_pts / option_delta          

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Underlying Points needed for Target:** {round(underlying_target_req, 2)}")
st.sidebar.markdown(f"**Underlying Points needed for SL:** {round(underlying_sl_req, 2)}")

# --- Data Loading Section ---
st.subheader("Step 1: Load 1-Minute Market Data")
data_source = st.radio("Select Data Source:", ["Fetch Today/Recent (yfinance)", "Upload Custom .TXT file"])

if data_source == "Fetch Today/Recent (yfinance)":
    period = st.selectbox("Select Timeframe", ["1d", "5d", "1mo"])
    if st.button("Fetch Live Data"):
        try:
            df = yf.download(ticker, period=period, interval="1m")
            if df.empty:
                st.error("No data found for this ticker.")
            else:
                df.reset_index(inplace=True)
                df['Time'] = pd.to_datetime(df['Datetime']).dt.strftime('%H:%M')
                st.session_state['market_data'] = df
                st.success(f"Successfully fetched {len(df)} rows of data for {ticker}.")
        except Exception as e:
            st.error(f"Failed to fetch data: {e}")

elif data_source == "Upload Custom .TXT file":
    uploaded_file = st.file_uploader("Upload .txt Data File (e.g., 2026 MAY NIFTY.txt)", type=["txt"])
    if uploaded_file is not None:
        try:
            # Parses the specific comma-separated format without headers from your uploaded text file
            df = pd.read_csv(
                uploaded_file, 
                header=None, 
                names=["Ticker", "Date", "Time", "Open", "High", "Low", "Close", "Volume", "OI"]
            )
            # Ensure time is zero-padded properly (e.g., "09:15")
            df['Time'] = df['Time'].astype(str).str.zfill(5) 
            st.session_state['market_data'] = df
            st.success(f"Successfully loaded {len(df)} rows from {uploaded_file.name}.")
        except Exception as e:
            st.error(f"Error parsing file: {e}. Please ensure it matches the comma-separated format.")

# --- Simulator Logic Section ---
st.subheader("Step 2: Enter Trading Signals")

# Only show the signal editor and run button if data is successfully loaded in session state
if st.session_state['market_data'] is not None and not st.session_state['market_data'].empty:
    
    df = st.session_state['market_data']
    
    default_signals = pd.DataFrame([
        {"Time": "09:21", "Action": "REVERSAL (LONG)"},
        {"Time": "09:56", "Action": "SHORT"},
        {"Time": "10:28", "Action": "LONG"},
        {"Time": "12:38", "Action": "SHORT"},
        {"Time": "14:23", "Action": "LONG"},
        {"Time": "14:45", "Action": "LONG"}
    ])
    
    edited_signals = st.data_editor(default_signals, num_rows="dynamic")
    
    if st.button("🚀 Run Simulation"):
        results = []
        total_pnl = 0
        total_slippage = 0
        
        for index, row in edited_signals.iterrows():
            signal_time = row['Time']
            action = row['Action']
            
            # Filter the dataframe for rows exactly at or after the signal time
            entry_data = df[df['Time'] >= signal_time]
            
            if entry_data.empty:
                results.append({
                    "Time": signal_time,
                    "Action": action,
                    "Entry Price": "-",
                    "Outcome": "Time Not Found",
                    "Net PnL (₹)": 0
                })
                continue
                
            entry_price = float(entry_data.iloc[0]['Close'])
            outcome = "Market Closed (Flat)"
            points_captured = 0
            max_favorable_move = 0 
            
            # Scan forward minute-by-minute
            for _, minute_data in entry_data.iterrows():
                current_price = float(minute_data['Close'])
                
                # Check for LONG positions
                if "LONG" in str(action).upper() or "REVERSAL" in str(action).upper():
                    current_move = current_price - entry_price
                    
                    if use_trailing:
                        max_favorable_move = max(max_favorable_move, current_move)
                        current_sl_line = max_favorable_move - underlying_sl_req
                        
                        if current_move >= underlying_target_req:
                            outcome = "Target Hit"
                            points_captured = option_target_pts
                            break
                        elif current_move <= current_sl_line:
                            outcome = "Trailing SL Hit" if max_favorable_move > 0 else "Initial SL Hit"
                            points_captured = current_sl_line * option_delta
                            break
                    else: # Fixed Target/SL
                        if current_move >= underlying_target_req:
                            outcome = "Target Hit"
                            points_captured = option_target_pts
                            break
                        elif current_move <= -underlying_sl_req:
                            outcome = "Stop Loss Hit"
                            points_captured = -option_sl_pts
                            break
                        
                # Check for SHORT positions
                elif "SHORT" in str(action).upper():
                    current_move = entry_price - current_price
                    
                    if use_trailing:
                        max_favorable_move = max(max_favorable_move, current_move)
                        current_sl_line = max_favorable_move - underlying_sl_req
                        
                        if current_move >= underlying_target_req:
                            outcome = "Target Hit"
                            points_captured = option_target_pts
                            break
                        elif current_move <= current_sl_line:
                            outcome = "Trailing SL Hit" if max_favorable_move > 0 else "Initial SL Hit"
                            points_captured = current_sl_line * option_delta
                            break
                    else: # Fixed Target/SL
                        if current_move >= underlying_target_req:
                            outcome = "Target Hit"
                            points_captured = option_target_pts
                            break
                        elif current_move <= -underlying_sl_req:
                            outcome = "Stop Loss Hit"
                            points_captured = -option_sl_pts
                            break
            
            # Financial calculations
            gross_pnl = points_captured * total_qty
            trade_turnover = (premium * total_qty) * 2
            slippage_cost = trade_turnover * (slippage_pct / 100)
            net_pnl = gross_pnl - slippage_cost - 40  # ₹40 base brokerage assumed
            
            total_pnl += net_pnl
            total_slippage += slippage_cost
            
            results.append({
                "Time": signal_time,
                "Action": action,
                "Entry (Spot)": round(entry_price, 2),
                "Outcome": outcome,
                "Opt Pts Captured": round(points_captured, 1),
                "Net PnL (₹)": round(net_pnl, 2)
            })
            
        # --- Display Dashboard Metrics ---
        st.subheader("Step 3: Simulation Results")
        st.dataframe(pd.DataFrame(results), use_container_width=True)
        
        col1, col2 = st.columns(2)
        col1.metric(label="Total Strategy Net PnL", value=f"₹ {round(total_pnl, 2)}")
        col2.metric(label="Slippage Friction Loss", value=f"₹ {round(total_slippage, 2)}")

else:
    st.info("Please load market data from Step 1 to proceed.")
