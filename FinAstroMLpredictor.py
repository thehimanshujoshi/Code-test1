"""
Financial Astrology ML Predictor – Streamlit Web App
Predicts market moves (rise, fall, gap up, etc.) for any ticker using
machine learning on astrological features.
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
from sklearn.metrics import classification_report, confusion_matrix
import warnings
import random

warnings.filterwarnings("ignore")

# ---------- Astrological utilities ----------
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

# Ruling planets for common indices/commodities
RULING = {
    "NIFTY": "Jupiter", "BANKNIFTY": "Venus", "SENSEX": "Jupiter",
    "GOLD": "Sun", "CRUDE": "Saturn", "SILVER": "Moon"
}

def nakshatra(lon):
    """Return Nakshatra name from ecliptic longitude (0-360)."""
    idx = int(lon // (360 / 27))
    return NAKSHATRAS[idx % 27]

def zodiac_sign(lon):
    idx = int(lon // 30)
    return ZODIAC[idx % 12]

def planet_position(planet_name, date):
    """Get ecliptic longitude of a planet for given date."""
    body = getattr(ephem, planet_name)() if planet_name != "Earth" else None
    body.compute(date)
    return np.degrees(body.elong) if planet_name == "Sun" else np.degrees(body.hlong)  # helio? use hlong for planets

def moon_phase(date):
    """Return moon illumination 0-1, 0=new, 0.5=quarter, 1=full."""
    moon = ephem.Moon()
    moon.compute(date)
    return moon.moon_phase

def retrograde(planet_name, date):
    """Check if planet is retrograde. Not defined for Sun/Moon."""
    if planet_name in ["Sun", "Moon"]:
        return False
    body = getattr(ephem, planet_name)()
    body.compute(date)
    # retrograde if ecliptic longitude is decreasing
    # Approximate by checking speed: negative for retro
    # pyephem doesn't directly give speed. Use two dates close together.
    dt = ephem.Date(date + 1/24)  # one hour later
    body2 = getattr(ephem, planet_name)()
    body2.compute(dt)
    return body2.hlong < body.hlong  # longitude decreased -> retro

def aspect_angle(planet1, planet2, date):
    """Compute angular separation (0-180) between two planets."""
    lon1 = planet_position(planet1, date)
    lon2 = planet_position(planet2, date)
    angle = abs(lon1 - lon2) % 360
    if angle > 180:
        angle = 360 - angle
    return angle

def major_aspect(angle, orb=6):
    """Return aspect string if angle within orb of major aspects."""
    aspects = {
        (0, 0): "Conjunction", (60, 60): "Sextile", (90, 90): "Square",
        (120, 120): "Trine", (180, 180): "Opposition"
    }
    for (low, high), name in aspects.items():
        if low - orb <= angle <= high + orb:
            return name
    return None

def void_of_course_moon(date, orb_hours=2):
    """Return True if Moon is void-of-course at given datetime (ephem.Date)."""
    moon = ephem.Moon()
    moon.compute(date)
    current_sign = ephem.constellation(moon)[1]  # sign name
    # Find time of next sign change
    start_date = ephem.Date(date)
    # search for Moon's next constellation change over next 2 days
    end_date = ephem.Date(date + 2)
    # ephem doesn't have direct next sign change, but we can loop
    t = start_date
    sign = current_sign
    next_sign_time = None
    while t < end_date:
        moon.compute(t)
        s = ephem.constellation(moon)[1]
        if s != sign:
            next_sign_time = t
            break
        t = ephem.Date(t + 10/1440)  # 10 minutes
    if next_sign_time is None:
        return False
    # Find last exact aspect before sign change
    last_aspect_time = None
    planets_to_check = ["Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
                        "Uranus", "Neptune", "Pluto"]
    for p in planets_to_check:
        # Search for aspect times using ephem.next_passage? We'll approximate by stepping
        t = start_date
        while t < next_sign_time:
            moon.compute(t)
            planet = getattr(ephem, p)()
            planet.compute(t)
            angle = np.degrees(moon.hlong) - np.degrees(planet.hlong)
            angle = abs(angle % 360)
            if angle > 180:
                angle = 360 - angle
            # if within 1 degree orb, consider exact
            if angle < 1:
                last_aspect_time = t
            t = ephem.Date(t + 5/1440)  # 5 min step
    if last_aspect_time is None:
        return True  # no aspects at all => VOC
    # If last aspect occurred before 'date', then Moon was VOC at that moment?
    return last_aspect_time < start_date

def compute_astro_features(dates):
    """Create a DataFrame of astrological features for each date."""
    rows = []
    for d in dates:
        dt = ephem.Date(d)
        row = {"date": d}
        # Planet longitudes & signs
        for p in PLANETS:
            lon = planet_position(p, dt)
            row[f"{p}_lon"] = lon
            row[f"{p}_sign"] = zodiac_sign(lon)
            row[f"{p}_nakshatra"] = nakshatra(lon)
            if p not in ["Sun", "Moon"]:
                row[f"{p}_retro"] = retrograde(p, dt)
        # Moon special
        row["moon_phase"] = moon_phase(dt)
        row["moon_voc"] = void_of_course_moon(dt)
        # Aspects between all planet pairs (just store counts/types later, but for ML we need numbers)
        # We'll create aspect features as one-hot or severity
        aspects = []
        for i, p1 in enumerate(PLANETS):
            for p2 in PLANETS[i+1:]:
                angle = aspect_angle(p1, p2, dt)
                asp = major_aspect(angle, orb=4)
                aspects.append(f"{p1}-{p2}_{asp}" if asp else f"{p1}-{p2}_none")
        # Convert aspects list to string features: we'll later one-hot encode, but for now store strings
        row["aspects"] = ";".join(aspects)
        rows.append(row)
    df = pd.DataFrame(rows)
    return df

# ---------- ML & Prediction ----------
def generate_synthetic_price(dates, trend=0.0, volatility=0.02):
    """Create a synthetic price series for demo purposes."""
    np.random.seed(42)
    prices = [100]
    for i in range(1, len(dates)):
        change = np.random.normal(trend, volatility)
        prices.append(prices[-1] * (1 + change))
    return np.array(prices)

def fetch_price_data(ticker, start, end):
    """Try to download data with yfinance, fallback to synthetic."""
    try:
        import yfinance as yf
        df = yf.download(ticker, start=start, end=end, progress=False)
        if df.empty:
            raise ValueError("No data")
        df = df[['Open', 'High', 'Low', 'Close']].dropna()
        return df
    except:
        st.warning(f"Could not fetch live data for {ticker}. Using synthetic data.")
        dates = pd.date_range(start, end, freq='B')
        closes = generate_synthetic_price(dates, trend=0.0002, volatility=0.015)
        df = pd.DataFrame({'Close': closes}, index=dates)
        df['Open'] = df['Close'].shift(1) * (1 + np.random.normal(0, 0.005, len(df)))
        df['High'] = df[['Open', 'Close']].max(axis=1) * (1 + abs(np.random.normal(0, 0.005, len(df))))
        df['Low'] = df[['Open', 'Close']].min(axis=1) * (1 - abs(np.random.normal(0, 0.005, len(df))))
        df = df.dropna()
        return df

def define_target(df, threshold=0.005):
    """Create multi-class target for next day."""
    df = df.copy()
    df['ret'] = df['Close'].pct_change()
    df['next_ret'] = df['ret'].shift(-1)
    df['gap'] = (df['Open'].shift(-1) - df['Close']) / df['Close']
    conditions = [
        (df['gap'] > threshold),  # gap up
        (df['gap'] < -threshold),  # gap down
        (df['next_ret'] > threshold),  # rise
        (df['next_ret'] < -threshold),  # fall
        (df['next_ret'].abs() <= threshold) & (df['gap'].abs() <= threshold)  # sideways
    ]
    choices = ['Gap Up', 'Gap Down', 'Rise', 'Fall', 'Sideways']
    df['label'] = np.select(conditions, choices, default='Sideways')
    # Add reversal detection: previous day down and today up, etc.
    df['prev_ret'] = df['ret']
    df['reversal_up'] = (df['prev_ret'] < -threshold) & (df['next_ret'] > threshold)
    df['reversal_down'] = (df['prev_ret'] > threshold) & (df['next_ret'] < -threshold)
    df.loc[df['reversal_up'], 'label'] = 'Reversal Up'
    df.loc[df['reversal_down'], 'label'] = 'Reversal Down'
    return df.dropna()

def train_model(feature_df, target_series):
    """Train Random Forest and return model, encoder, feature names."""
    # One-hot encode aspects and sign features
    X = pd.get_dummies(feature_df.drop(columns=['date', 'aspects']), columns=['aspects'])
    le = LabelEncoder()
    y = le.fit_transform(target_series)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    acc = model.score(X_test, y_test)
    st.session_state['model_acc'] = acc
    return model, le, X.columns

def predict_next(model, le, feature_df_latest, feature_columns):
    """Predict next day's market move probabilities."""
    X_latest = pd.get_dummies(feature_df_latest.drop(columns=['date', 'aspects']), columns=['aspects'])
    X_latest = X_latest.reindex(columns=feature_columns, fill_value=0)
    probs = model.predict_proba(X_latest)[0]
    pred_idx = np.argmax(probs)
    pred_label = le.inverse_transform([pred_idx])[0]
    return pred_label, probs, le.classes_

def feature_importance_text(model, feature_names, le, top_n=10):
    """Return a DataFrame of top features with astrological explanation."""
    importance = model.feature_importances_
    indices = np.argsort(importance)[::-1][:top_n]
    rows = []
    for idx in indices:
        name = feature_names[idx]
        imp = importance[idx]
        # Parse astrological meaning
        desc = "Astrological factor: "
        if "_retro" in name:
            planet = name.split("_")[0]
            desc += f"{planet} retrograde"
        elif "_sign" in name:
            planet, sign = name.split("_")[0], name.split("_")[-1]
            desc += f"{planet} in {sign}"
        elif "_nakshatra" in name:
            planet, nak = name.split("_")[0], name.split("_")[-1]
            desc += f"{planet} in {nak} Nakshatra"
        elif "moon_voc" in name:
            desc += "Moon Void-of-Course"
        elif "moon_phase" in name:
            desc += "Moon Phase"
        elif "aspects_" in name:
            # extract aspect string
            asp = name.replace("aspects_", "")
            desc += f"Aspect {asp}"
        else:
            desc += name
        rows.append({"Feature": name, "Importance": f"{imp:.4f}", "Interpretation": desc})
    return pd.DataFrame(rows)

# ---------- Streamlit UI ----------
st.set_page_config(page_title="Astro-ML Market Oracle", layout="wide")
st.title("🔮 Financial Astrology & ML Market Predictor")
st.markdown("Predict next-day market moves (Rise, Fall, Gap Up, Reversal, etc.) using a Random Forest trained on planetary positions, aspects, retrogrades, Nakshatras, and more.")

# Sidebar inputs
ticker = st.sidebar.text_input("Ticker Symbol", value="NIFTY").upper()
start_date = st.sidebar.date_input("Start Date", datetime(2020, 1, 1))
end_date = st.sidebar.date_input("End Date", datetime.today())
predict_date = st.sidebar.date_input("Prediction Date (next trading day)", datetime.today() + timedelta(days=1))

st.sidebar.markdown("---")
st.sidebar.info("This app uses synthetic data if live data unavailable. Astrological calculations are approximate.")

# Load data and train
@st.cache_resource
def load_and_train(ticker, start, end):
    price_df = fetch_price_data(ticker, start, end)
    # Compute astro features for each trading day
    dates = price_df.index.tolist()
    astro_df = compute_astro_features(dates)
    # Prepare target
    target_df = define_target(price_df)
    common_dates = target_df.index.intersection(astro_df['date'])
    astro_df = astro_df[astro_df['date'].isin(common_dates)].reset_index(drop=True)
    target_df = target_df.loc[common_dates].reset_index(drop=True)
    # Train model
    model, le, feature_cols = train_model(astro_df, target_df['label'])
    return model, le, feature_cols, astro_df, target_df, price_df

if st.sidebar.button("Train Model & Analyse"):
    with st.spinner("Calculating planetary positions and training ML model..."):
        try:
            model, le, feature_cols, astro_df, target_df, price_df = load_and_train(ticker, start_date, end_date)
            st.session_state['model'] = model
            st.session_state['le'] = le
            st.session_state['feature_cols'] = feature_cols
            st.session_state['astro_df'] = astro_df
            st.session_state['target_df'] = target_df
            st.session_state['price_df'] = price_df
            st.success(f"Model trained. Accuracy on test set: {st.session_state.get('model_acc', 0):.2%}")
        except Exception as e:
            st.error(f"Error: {e}")

if 'model' in st.session_state:
    model = st.session_state.model
    le = st.session_state.le
    feature_cols = st.session_state.feature_cols
    astro_df = st.session_state.astro_df
    target_df = st.session_state.target_df
    price_df = st.session_state.price_df

    # Predict next day
    # Get astro features for prediction date
    pred_dt = ephem.Date(predict_date)
    pred_feat = compute_astro_features([predict_date])
    if not pred_feat.empty:
        pred_label, probs, classes = predict_next(model, le, pred_feat, feature_cols)

        col1, col2 = st.columns([1, 1])
        with col1:
            st.subheader("📈 Next‑Day Prediction")
            st.metric("Predicted Move", pred_label)
            prob_df = pd.DataFrame({"Class": classes, "Probability": probs}).set_index("Class")
            st.bar_chart(prob_df)

        with col2:
            st.subheader("✨ Top Astrological Drivers")
            imp_df = feature_importance_text(model, feature_cols, le, top_n=8)
            st.dataframe(imp_df, use_container_width=True)

        # Detailed astro‑events for prediction date
        st.subheader(f"🌟 Astrological Events on {predict_date}")
        pred_feat_exp = pred_feat.iloc[0]
        # Planet positions
        cols = st.columns(3)
        for i, p in enumerate(PLANETS):
            lon = pred_feat_exp[f"{p}_lon"]
            sign = pred_feat_exp[f"{p}_sign"]
            nak = pred_feat_exp[f"{p}_nakshatra"]
            retro = pred_feat_exp.get(f"{p}_retro", False)
            retro_str = " ℞" if retro else ""
            cols[i % 3].metric(f"{p}{retro_str}", f"{lon:.1f}°", f"{sign} / {nak}")

        # Major aspects
        st.write("**Major Aspects (orb ≤6°)**")
        aspect_list = pred_feat_exp['aspects'].split(';')
        major_aspects = [a for a in aspect_list if not a.endswith('_none')]
        if major_aspects:
            st.write(", ".join(major_aspects))
        else:
            st.write("No exact major aspects.")

        # Moon special
        st.write(f"🌙 Moon Phase: {pred_feat_exp['moon_phase']:.2f} (0=new, 1=full)")
        st.write(f"🌑 Moon Void-of-Course: {'Yes' if pred_feat_exp['moon_voc'] else 'No'}")

        # First‑Trade horoscope for known tickers
        rule = RULING.get(ticker, None)
        if rule:
            st.subheader("🏛️ First‑Trade Ruling Planet Insight")
            st.markdown(f"The ruling planet for **{ticker}** is **{rule}**. Pay special attention to its transits and aspects.")
            # Show ruling planet's current position
            rul_lon = pred_feat_exp[f"{rule}_lon"]
            rul_sign = pred_feat_exp[f"{rule}_sign"]
            rul_retro = pred_feat_exp.get(f"{rule}_retro", False)
            st.write(f"Current {rule}: {rul_lon:.1f}° in {rul_sign} {'(Retrograde)' if rul_retro else ''}")

        # Planetary Price levels (converting degrees to price)
        st.subheader("💹 Planetary Price Conversion (Support/Resistance)")
        # Crude rule: use last close price as anchor
        if not price_df.empty:
            last_close = price_df['Close'].iloc[-1]
            levels = {}
            for p in PLANETS:
                lon = pred_feat_exp[f"{p}_lon"]
                # Convert degree to price: a simple mapping (0-360 -> scaled to price range)
                price_level = last_close * (1 + (lon - 180)/3600)  # arbitrary scaling
                levels[p] = price_level
            level_df = pd.DataFrame(levels.items(), columns=["Planet", "Derived Price Level"])
            st.dataframe(level_df.style.format({"Derived Price Level": "{:.2f}"}), use_container_width=True)

        # Advanced harmonic view
        st.subheader("🎶 Planetary Harmonics")
        # List planet pairs that are in harmonic angles (0, 45, 72, 90, 120, 150, 180) within 2° orb
        harmonic_text = []
        for i, p1 in enumerate(PLANETS):
            for p2 in PLANETS[i+1:]:
                angle = aspect_angle(p1, p2, pred_dt)
                if any(abs(angle - h) <= 2 for h in [0, 45, 72, 90, 120, 150, 180]):
                    harmonic_text.append(f"{p1}-{p2}: {angle:.1f}°")
        if harmonic_text:
            st.write("Harmonic pairs (orb 2°):")
            st.write(", ".join(harmonic_text))
        else:
            st.write("No harmonic pair within tight orb.")

        # Time-series of planetary positions
        st.subheader("📊 Planetary Longitudes Over Time")
        fig = go.Figure()
        for p in PLANETS[:6]:  # inner planets for clarity
            fig.add_trace(go.Scatter(x=astro_df['date'], y=astro_df[f'{p}_lon'], mode='lines', name=p))
        fig.update_layout(title="Planetary Longitudes (0-360°)", xaxis_title="Date", yaxis_title="Degrees")
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.error("Could not compute features for prediction date.")