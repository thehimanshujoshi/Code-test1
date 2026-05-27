"""
Financial Astrology ML Predictor – Streamlit Web App
Predicts market moves (Rise, Fall, Gap Up, Reversal, etc.) for any ticker using
machine learning on true geocentric astrological features.
Optimised for speed and accuracy.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import ephem
import plotly.graph_objects as go
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import warnings
import random
import math

warnings.filterwarnings("ignore")

# ================== CONSTANTS ==================
NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha",
    "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha",
    "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada",
    "Uttara Bhadrapada", "Revati"
]

ZODIAC = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
          "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter",
           "Saturn", "Uranus", "Neptune", "Pluto"]

RULING = {
    "NIFTY": "Jupiter", "BANKNIFTY": "Venus", "SENSEX": "Jupiter",
    "GOLD": "Sun", "CRUDE": "Saturn", "SILVER": "Moon"
}

# ============== ASTROLOGICAL UTILITIES (GEOCENTRIC) ==============
# Observer at Earth's centre for true geocentric positions
GEO_OBS = ephem.Observer()
GEO_OBS.elevation = -6371000  # metres, approximate Earth radius

def geocentric_lon(planet_name, date):
    """Return geocentric ecliptic longitude (degrees) of a planet."""
    body = getattr(ephem, planet_name)()
    body.compute(date)  # heliocentric, but we override with observer
    body.compute(GEO_OBS)
    # Convert geocentric RA/Dec to ecliptic longitude
    eq = ephem.Equatorial(body.a_ra, body.a_dec, epoch=ephem.J2000)
    ecl = ephem.Ecliptic(eq)
    return np.degrees(ecl.lon)

def nakshatra(lon):
    idx = int(lon // (360.0 / 27))
    return NAKSHATRAS[idx % 27]

def zodiac_sign(lon):
    idx = int(lon // 30)
    return ZODIAC[idx % 12]

def moon_phase(date):
    moon = ephem.Moon()
    moon.compute(GEO_OBS)
    return moon.moon_phase

def retrograde(planet_name, date_prev, date_curr):
    """Check if planet is retrograde by comparing longitudes at two close dates."""
    lon_prev = geocentric_lon(planet_name, date_prev)
    lon_curr = geocentric_lon(planet_name, date_curr)
    # account for crossing 360°
    diff = (lon_curr - lon_prev + 360) % 360
    # moving backwards if diff > 180 (actually we want if diff < 0, but wrap)
    # Proper: if the short way around is negative
    return (lon_curr - lon_prev) < 0 and abs(lon_curr - lon_prev) < 1.0  # less than 1° per hour

def aspect_angle(lon1, lon2):
    """Angular separation (0-180) between two longitudes."""
    angle = abs(lon1 - lon2) % 360
    if angle > 180:
        angle = 360 - angle
    return angle

def major_aspect(angle, orb=4):
    aspects = {
        (0, 0): "Conjunction", (60, 60): "Sextile", (90, 90): "Square",
        (120, 120): "Trine", (180, 180): "Opposition"
    }
    for (low, high), name in aspects.items():
        if low - orb <= angle <= high + orb:
            return name
    return None

def is_voc_moon_prediction(date):
    """Heavy VOC check – only for the prediction date."""
    moon = ephem.Moon()
    # find next sign change
    dt = ephem.Date(date)
    # current sign
    moon.compute(GEO_OBS)
    current_sign = zodiac_sign(np.degrees(ephem.Ecliptic(ephem.Equatorial(moon.a_ra, moon.a_dec, epoch=ephem.J2000)).lon))
    next_sign_time = None
    t = dt
    while t < ephem.Date(dt + 2):
        moon.compute(GEO_OBS)
        ecl = ephem.Ecliptic(ephem.Equatorial(moon.a_ra, moon.a_dec, epoch=ephem.J2000))
        lon = np.degrees(ecl.lon)
        s = zodiac_sign(lon)
        if s != current_sign:
            next_sign_time = t
            break
        t = ephem.Date(t + 10/1440)  # +10 minutes
    if next_sign_time is None:
        return False
    # last major aspect before sign change
    for p in PLANETS:
        if p == "Moon":
            continue
        body = getattr(ephem, p)()
        t = dt
        last_aspect_time = None
        while t < next_sign_time:
            moon.compute(GEO_OBS)
            body.compute(GEO_OBS)
            m_lon = np.degrees(ephem.Ecliptic(ephem.Equatorial(moon.a_ra, moon.a_dec, epoch=ephem.J2000)).lon)
            p_lon = np.degrees(ephem.Ecliptic(ephem.Equatorial(body.a_ra, body.a_dec, epoch=ephem.J2000)).lon)
            angle = aspect_angle(m_lon, p_lon)
            if angle < 1:
                last_aspect_time = t
            t = ephem.Date(t + 5/1440)
        if last_aspect_time and last_aspect_time > dt:
            return False  # aspect after current time, so not VOC
    return True  # no aspects before sign change

# ================== FEATURE COMPUTATION ==================
def compute_astro_features(dates, progress_callback=None):
    """Build DataFrame of astrological features for list of dates.
       progress_callback: optional function(float 0-1)"""
    rows = []
    total = len(dates)
    for i, d in enumerate(dates):
        dt = ephem.Date(d)
        dt_plus1hr = ephem.Date(d + 1/24)
        row = {"date": d}
        lons = {}
        # compute all geocentric longitudes
        for p in PLANETS:
            lon = geocentric_lon(p, dt)
            lons[p] = lon
            row[f"{p}_lon"] = lon
            row[f"{p}_sign"] = zodiac_sign(lon)
            row[f"{p}_nakshatra"] = nakshatra(lon)
        # retrogrades
        for p in PLANETS:
            if p in ["Sun", "Moon"]:
                row[f"{p}_retro"] = False
            else:
                # compare longitudes at dt and dt+1hr
                lon1 = lons[p]
                lon2 = geocentric_lon(p, dt_plus1hr)
                diff = (lon2 - lon1 + 360) % 360
                # retrograde if longitude decreased and it's not a wrap (diff < 180 implies negative motion)
                row[f"{p}_retro"] = lon2 < lon1  # simpler, assuming no fast wrap
        # Moon phase & VOC (VOC set to False for training data)
        row["moon_phase"] = moon_phase(dt)
        row["moon_voc"] = False  # we skip heavy VOC for historical data
        # Aspects
        aspect_list = []
        for i_p1, p1 in enumerate(PLANETS):
            for p2 in PLANETS[i_p1+1:]:
                angle = aspect_angle(lons[p1], lons[p2])
                asp = major_aspect(angle, orb=4)
                aspect_list.append(f"{p1}-{p2}_{asp}" if asp else f"{p1}-{p2}_none")
        row["aspects"] = ";".join(aspect_list)
        rows.append(row)
        if progress_callback:
            progress_callback((i+1)/total)
    return pd.DataFrame(rows)

# ================== DATA & TARGET ==================
def generate_synthetic_price(dates, trend=0.0002, volatility=0.015):
    np.random.seed(42)
    prices = [100]
    for _ in range(1, len(dates)):
        prices.append(prices[-1] * (1 + np.random.normal(trend, volatility)))
    return np.array(prices)

def fetch_price_data(ticker, start, end):
    try:
        import yfinance as yf
        df = yf.download(ticker, start=start, end=end, progress=False)
        if df.empty:
            raise ValueError("No data")
        df = df[['Open', 'High', 'Low', 'Close']].dropna()
        return df
    except Exception:
        st.warning(f"Could not fetch live data for {ticker}. Using synthetic data.")
        dates = pd.date_range(start, end, freq='B')
        closes = generate_synthetic_price(dates)
        df = pd.DataFrame({'Close': closes}, index=dates)
        df['Open'] = df['Close'].shift(1) * (1 + np.random.normal(0, 0.005, len(df)))
        df['High'] = df[['Open', 'Close']].max(axis=1) * (1 + abs(np.random.normal(0, 0.005, len(df))))
        df['Low'] = df[['Open', 'Close']].min(axis=1) * (1 - abs(np.random.normal(0, 0.005, len(df))))
        df = df.dropna()
        return df

def define_target(df, threshold=0.005):
    df = df.copy()
    df['ret'] = df['Close'].pct_change()
    df['next_ret'] = df['ret'].shift(-1)
    df['gap'] = (df['Open'].shift(-1) - df['Close']) / df['Close']
    conditions = [
        (df['gap'] > threshold),
        (df['gap'] < -threshold),
        (df['next_ret'] > threshold),
        (df['next_ret'] < -threshold),
        (df['next_ret'].abs() <= threshold) & (df['gap'].abs() <= threshold)
    ]
    choices = ['Gap Up', 'Gap Down', 'Rise', 'Fall', 'Sideways']
    df['label'] = np.select(conditions, choices, default='Sideways')
    df['prev_ret'] = df['ret']
    df['reversal_up'] = (df['prev_ret'] < -threshold) & (df['next_ret'] > threshold)
    df['reversal_down'] = (df['prev_ret'] > threshold) & (df['next_ret'] < -threshold)
    df.loc[df['reversal_up'], 'label'] = 'Reversal Up'
    df.loc[df['reversal_down'], 'label'] = 'Reversal Down'
    return df.dropna()

# ================== ML TRAINING ==================
def train_model(feature_df, target_series):
    X = pd.get_dummies(feature_df.drop(columns=['date', 'aspects']), columns=['aspects'])
    le = LabelEncoder()
    y = le.fit_transform(target_series)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    acc = model.score(X_test, y_test)
    return model, le, X.columns, acc

def predict_next(model, le, feature_df_latest, feature_columns):
    X_latest = pd.get_dummies(feature_df_latest.drop(columns=['date', 'aspects']), columns=['aspects'])
    X_latest = X_latest.reindex(columns=feature_columns, fill_value=0)
    probs = model.predict_proba(X_latest)[0]
    pred_idx = np.argmax(probs)
    pred_label = le.inverse_transform([pred_idx])[0]
    return pred_label, probs, le.classes_

def feature_importance_text(model, feature_names, top_n=10):
    importance = model.feature_importances_
    indices = np.argsort(importance)[::-1][:top_n]
    rows = []
    for idx in indices:
        name = feature_names[idx]
        imp = importance[idx]
        desc = "Astrological factor: "
        if "_retro" in name:
            planet = name.split("_")[0]
            desc += f"{planet} retrograde"
        elif "_sign" in name:
            parts = name.split("_")
            planet, sign = parts[0], parts[-1]
            desc += f"{planet} in {sign}"
        elif "_nakshatra" in name:
            parts = name.split("_")
            planet, nak = parts[0], parts[-1]
            desc += f"{planet} in {nak}"
        elif "moon_voc" in name:
            desc += "Moon Void-of-Course"
        elif "moon_phase" in name:
            desc += "Moon Phase"
        elif "aspects_" in name:
            asp = name.replace("aspects_", "")
            desc += f"Aspect {asp}"
        else:
            desc += name
        rows.append({"Feature": name, "Importance": f"{imp:.4f}", "Interpretation": desc})
    return pd.DataFrame(rows)

# ================== STREAMLIT UI ==================
st.set_page_config(page_title="Astro-ML Market Oracle", layout="wide")
st.title("🔮 Financial Astrology & ML Market Predictor")
st.markdown("Predict next‑day market moves using a Random Forest trained on **geocentric** planetary positions, Nakshatras, retrogrades, and aspects.")

# Sidebar
ticker = st.sidebar.text_input("Ticker Symbol", value="NIFTY").upper()
start_date = st.sidebar.date_input("Start Date", datetime(2020, 1, 1))
end_date = st.sidebar.date_input("End Date", datetime.today())
predict_date = st.sidebar.date_input("Prediction Date (next trading day)", datetime.today() + timedelta(days=1))
st.sidebar.markdown("---")
st.sidebar.info("Synthetic data used if live data unavailable. Astrological calculations are geocentric and approximate.")

if st.sidebar.button("Train Model & Analyse"):
    with st.spinner("Fetching data and computing astrological features..."):
        # Fetch price data
        price_df = fetch_price_data(ticker, start_date, end_date)
        dates = price_df.index.tolist()

        # Progress bar for feature generation
        progress_bar = st.progress(0)
        status_text = st.empty()

        def update_progress(frac):
            progress_bar.progress(frac)
            status_text.text(f"Generating astro features... {frac:.0%}")

        astro_df = compute_astro_features(dates, progress_callback=update_progress)
        status_text.text("Astro features complete.")
        progress_bar.empty()

        # Target definition
        target_df = define_target(price_df)
        common_dates = target_df.index.intersection(astro_df['date'])
        astro_df = astro_df[astro_df['date'].isin(common_dates)].reset_index(drop=True)
        target_df = target_df.loc[common_dates].reset_index(drop=True)

        # Train model
        with st.spinner("Training Random Forest model..."):
            model, le, feature_cols, acc = train_model(astro_df, target_df['label'])

        st.success(f"Model trained. Test accuracy: {acc:.2%}")

        # Save in session
        st.session_state['model'] = model
        st.session_state['le'] = le
        st.session_state['feature_cols'] = feature_cols
        st.session_state['astro_df'] = astro_df
        st.session_state['target_df'] = target_df
        st.session_state['price_df'] = price_df
        st.session_state['last_close'] = price_df['Close'].iloc[-1]

# If model exists, show predictions
if 'model' in st.session_state:
    model = st.session_state.model
    le = st.session_state.le
    feature_cols = st.session_state.feature_cols
    astro_df = st.session_state.astro_df
    target_df = st.session_state.target_df
    price_df = st.session_state.price_df
    last_close = st.session_state.last_close

    # Compute features for prediction date (include VOC)
    pred_feat = compute_astro_features([predict_date])
    pred_feat.at[0, 'moon_voc'] = is_voc_moon_prediction(predict_date)
    pred_label, probs, classes = predict_next(model, le, pred_feat, feature_cols)

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("📈 Next‑Day Prediction")
        st.metric("Predicted Move", pred_label)
        prob_df = pd.DataFrame({"Class": classes, "Probability": probs}).set_index("Class")
        st.bar_chart(prob_df)

    with col2:
        st.subheader("✨ Top Astrological Drivers")
        imp_df = feature_importance_text(model, feature_cols, top_n=8)
        st.dataframe(imp_df, use_container_width=True)

    # Detailed astro events
    st.subheader(f"🌟 Astrological Events on {predict_date}")
    pred_row = pred_feat.iloc[0]
    cols = st.columns(3)
    for i, p in enumerate(PLANETS):
        lon = pred_row[f"{p}_lon"]
        sign = pred_row[f"{p}_sign"]
        nak = pred_row[f"{p}_nakshatra"]
        retro = pred_row[f"{p}_retro"]
        retro_str = " ℞" if retro else ""
        cols[i % 3].metric(f"{p}{retro_str}", f"{lon:.1f}°", f"{sign} / {nak}")

    st.write("**Major Aspects (orb ≤4°)**")
    aspect_list = pred_row['aspects'].split(';')
    major_asp = [a for a in aspect_list if not a.endswith('_none')]
    if major_asp:
        st.write(", ".join(major_asp))
    else:
        st.write("No exact major aspects.")

    st.write(f"🌙 Moon Phase: {pred_row['moon_phase']:.2f} (0=new, 1=full)")
    st.write(f"🌑 Moon Void-of-Course: {'Yes' if pred_row['moon_voc'] else 'No'}")

    rule = RULING.get(ticker, None)
    if rule:
        st.subheader("🏛️ First‑Trade Ruling Planet Insight")
        st.markdown(f"The ruling planet for **{ticker}** is **{rule}**.")
        rul_lon = pred_row[f"{rule}_lon"]
        rul_sign = pred_row[f"{rule}_sign"]
        rul_retro = pred_row[f"{rule}_retro"]
        st.write(f"Current {rule}: {rul_lon:.1f}° in {rul_sign} {'(Retrograde)' if rul_retro else ''}")

    # Planetary Price Levels
    st.subheader("💹 Planetary Price Conversion (Support/Resistance)")
    levels = {}
    for p in PLANETS:
        lon = pred_row[f"{p}_lon"]
        price_level = last_close * (1 + (lon - 180) / 3600)  # simple scaling
        levels[p] = price_level
    level_df = pd.DataFrame(levels.items(), columns=["Planet", "Derived Price Level"])
    st.dataframe(level_df.style.format({"Derived Price Level": "{:.2f}"}), use_container_width=True)

    # Planetary Harmonics
    st.subheader("🎶 Planetary Harmonics (tight orb 2°)")
    harmonic_text = []
    for i, p1 in enumerate(PLANETS):
        for p2 in PLANETS[i+1:]:
            angle = aspect_angle(pred_row[f"{p1}_lon"], pred_row[f"{p2}_lon"])
            if any(abs(angle - h) <= 2 for h in [0, 45, 72, 90, 120, 150, 180]):
                harmonic_text.append(f"{p1}-{p2}: {angle:.1f}°")
    if harmonic_text:
        st.write(", ".join(harmonic_text))
    else:
        st.write("None")

    # Chart of planetary longitudes
    st.subheader("📊 Planetary Longitudes Over Training Period")
    fig = go.Figure()
    for p in PLANETS[:6]:
        fig.add_trace(go.Scatter(x=astro_df['date'], y=astro_df[f'{p}_lon'], mode='lines', name=p))
    fig.update_layout(title="Geocentric Longitudes (0-360°)", xaxis_title="Date", yaxis_title="Degrees")
    st.plotly_chart(fig, use_container_width=True)