import streamlit as st
import swisseph as swe
import pandas as pd
import math
from datetime import datetime
import pytz
import re
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

# ==========================================
# 1. CONFIGURATION & CONSTANTS
# ==========================================
st.set_page_config(page_title="Ultimate Prashna Engine", layout="wide", page_icon="🕉️")

swe.set_sid_mode(swe.SIDM_LAHIRI)

PLANETS = {
    0: 'Sun', 1: 'Moon', 2: 'Mercury', 3: 'Venus', 
    4: 'Mars', 5: 'Jupiter', 6: 'Saturn', 
    10: 'Rahu', 11: 'Ketu' 
}

ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", 
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

RASHI_LORDS = {
    0: 'Mars', 1: 'Venus', 2: 'Mercury', 3: 'Moon', 4: 'Sun', 5: 'Mercury',
    6: 'Venus', 7: 'Mars', 8: 'Jupiter', 9: 'Saturn', 10: 'Saturn', 11: 'Jupiter'
}

PLANET_ORBS = {
    'Sun': 15.0, 'Moon': 12.0, 'Mars': 8.0, 'Mercury': 7.0,
    'Jupiter': 9.0, 'Venus': 7.0, 'Saturn': 9.0, 'Rahu': 0.0, 'Ketu': 0.0
}

# Added Modalities for Timing Predictions
MODALITIES = {
    "Aries": "Movable", "Taurus": "Fixed", "Gemini": "Dual",
    "Cancer": "Movable", "Leo": "Fixed", "Virgo": "Dual",
    "Libra": "Movable", "Scorpio": "Fixed", "Sagittarius": "Dual",
    "Capricorn": "Movable", "Aquarius": "Fixed", "Pisces": "Dual"
}

CITY_DB = {
    "Jaipur, Rajasthan (Default)": {"lat": 26.9124, "lon": 75.7873},
    "New Delhi, Delhi": {"lat": 28.6139, "lon": 77.2090},
    "Mumbai, Maharashtra": {"lat": 19.0760, "lon": 72.8777},
    "Bangalore, Karnataka": {"lat": 12.9716, "lon": 77.5946},
    "Chennai, Tamil Nadu": {"lat": 13.0827, "lon": 80.2707},
    "Kolkata, West Bengal": {"lat": 22.5726, "lon": 88.3639},
    "Custom Search...": None
}

# ==========================================
# 2. ADVANCED NLP KEYWORD ENGINE
# ==========================================
def extract_target_house(query):
    query = query.lower()
    
    house_keywords = {
        1: ['myself', 'health', 'life', 'appearance', 'body', 'me', 'i ', 'my ', 'recover', 'safe', 'danger'],
        2: ['money', 'wealth', 'salary', 'bank', 'finance', 'speech', 'family', 'saving', 'jewelry', 'gold', 'buying', 'selling'],
        3: ['brother', 'sister', 'sibling', 'trip', 'travel', 'neighbor', 'email', 'message', 'courage', 'interview', 'document', 'contract', 'news'],
        4: ['mother', 'house', 'home', 'real estate', 'property', 'car', 'vehicle', 'land', 'rain', 'weather', 'storm', 'climate', 'stolen', 'lost', 'found'],
        5: ['child', 'baby', 'son', 'daughter', 'exam', 'lottery', 'romance', 'love', 'dating', 'stock', 'crypto', 'pregnancy', 'sports', 'entertainment'],
        6: ['disease', 'sick', 'illness', 'pet', 'dog', 'cat', 'enemy', 'court', 'debt', 'loan', 'surgery', 'tenant', 'competition', 'lawsuit', 'dispute'],
        7: ['marriage', 'husband', 'wife', 'partner', 'business partner', 'divorce', 'relationship', 'spouse', 'deal', 'agreement', 'thief', 'lawyer'],
        8: ['death', 'inheritance', 'occult', 'sudden', 'accident', 'surgery', 'tax', 'insurance', 'alimony', 'mystery', 'secret', 'bankruptcy'],
        9: ['university', 'college', 'visa', 'abroad', 'religion', 'father', 'guru', 'long trip', 'pilgrimage', 'luck', 'master', 'astrology', 'god'],
        10: ['job', 'career', 'promotion', 'boss', 'government', 'profession', 'status', 'business', 'fame', 'company', 'judge', 'authority'],
        11: ['friend', 'profit', 'gain', 'desire', 'wish', 'elder', 'income', 'network', 'award', 'bonus', 'success'],
        12: ['hospital', 'jail', 'prison', 'loss', 'foreign', 'hidden enemy', 'sleep', 'spiritual', 'ashram', 'expense', 'charity', 'give up']
    }
    
    for house, keywords in house_keywords.items():
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', query):
                return house, keyword
                
    return 1, "general situation / self"

# ==========================================
# 3. CORE ASTRONOMICAL CALCULATIONS
# ==========================================
@st.cache_data(ttl=3600)
def geocode_location(city_name):
    geolocator = Nominatim(user_agent="prashna_pro_engine")
    location = geolocator.geocode(city_name)
    if location:
        return location.latitude, location.longitude
    return None, None

def get_julian_day(dt, lat, lon):
    tf = TimezoneFinder()
    tz_str = tf.timezone_at(lng=lon, lat=lat) or "UTC"
    local_tz = pytz.timezone(tz_str)
    
    if dt.tzinfo is None:
        local_dt = local_tz.localize(dt)
    else:
        local_dt = dt
        
    utc_dt = local_dt.astimezone(pytz.utc)
    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, 
                    utc_dt.hour + utc_dt.minute/60.0 + utc_dt.second/3600.0)
    return jd, tz_str

def calculate_chart(jd, lat, lon):
    positions = {}
    flag = swe.FLG_SWIEPH | swe.FLG_SIDEREAL 
    
    for p_id, p_name in PLANETS.items():
        if p_id == 10:
            calc, _ = swe.calc_ut(jd, swe.TRUE_NODE, flag)
        elif p_id == 11:
            calc_rahu, _ = swe.calc_ut(jd, swe.TRUE_NODE, flag)
            calc = ((calc_rahu[0] + 180.0) % 360.0, 0, 0, 0, 0, 0)
        else:
            calc, _ = swe.calc_ut(jd, p_id, flag)
            
        lon_deg = calc[0]
        lat_deg = calc[1] 
        speed = calc[3]
        sign_idx = int(lon_deg // 30)
        sign_name = ZODIAC_SIGNS[sign_idx]
        
        positions[p_name] = {
            'Longitude': lon_deg,
            'Latitude': lat_deg,
            'Sign': sign_name,
            'Modality': MODALITIES[sign_name],
            'Degree': lon_deg % 30,
            'Speed': speed,
            'Retrograde': speed < 0
        }
        
    cusps, ascmc = swe.houses_ex(jd, lat, lon, b'W', flag)
    asc_deg = ascmc[0]
    return positions, asc_deg

def check_aspect(p1, p2, positions):
    """Helper function to check exact aspects with orbs."""
    orb1, orb2 = PLANET_ORBS[p1], PLANET_ORBS[p2]
    avg_orb = (orb1 + orb2) / 2.0
    angle = abs(positions[p1]['Longitude'] - positions[p2]['Longitude'])
    if angle > 180: angle = 360 - angle
    
    aspects = {0: 'Conjunction', 60: 'Sextile', 90: 'Square', 120: 'Trine', 180: 'Opposition'}
    for asp_deg, asp_name in aspects.items():
        if abs(angle - asp_deg) <= avg_orb:
            return True, asp_name, avg_orb
    return False, None, None

# ==========================================
# 4. EXHAUSTIVE PRASHNA RULES ENGINE
# ==========================================
def evaluate_horary_depth(positions, lagnesh, karyesh, target_house):
    report = {}
    
    # 1. Modality & Timing
    karyesh_mod = positions[karyesh]['Modality']
    if karyesh_mod == "Movable":
        report['Timing'] = "Things will move quickly. Situations are subject to rapid change."
    elif karyesh_mod == "Fixed":
        report['Timing'] = "The situation is stuck or stable. Results will be slow, or current conditions will persist."
    else:
        report['Timing'] = "Mixed results. The situation is fluid and could go back and forth."

    # 2. Retrograde Check (Delays/Returns)
    if positions[karyesh]['Retrograde']:
        report['Retrograde'] = f"The planet ruling this matter ({karyesh}) is Retrograde. This indicates delays, needing to re-do something, or the return of a past person/situation."
    else:
        report['Retrograde'] = "Forward momentum is present."

    # 3. Tajika Yogas (Direct Connection)
    if lagnesh == karyesh:
        report['Verdict'] = "YES / FAVORABLE"
        report['Reason'] = "The energies are perfectly aligned. The outcome is highly favorable and naturally manifesting (Self-Signification)."
        report['Yoga'] = "Self-Signification"
        return report
        
    has_aspect, asp_name, orb = check_aspect(lagnesh, karyesh, positions)
    
    if has_aspect:
        p1, p2 = positions[lagnesh], positions[karyesh]
        fast_p, slow_p = (p1, p2) if abs(p1['Speed']) > abs(p2['Speed']) else (p2, p1)
        if fast_p['Degree'] < slow_p['Degree']:
            report['Verdict'] = "YES / SUCCESS"
            report['Reason'] = f"The necessary connection is being made. Success is indicated via a direct applying aspect."
            report['Yoga'] = f"Ithasala ({asp_name})"
        else:
            report['Verdict'] = "NO / DELAYED"
            report['Reason'] = "The opportunity has recently passed, or there is an active separation happening."
            report['Yoga'] = f"Easarpha ({asp_name})"
    else:
        # 4. Nakta Yoga (Translation of Light via Moon)
        # If no direct aspect, does the Moon aspect both?
        if lagnesh != 'Moon' and karyesh != 'Moon':
            moon_lag, _, _ = check_aspect('Moon', lagnesh, positions)
            moon_kar, _, _ = check_aspect('Moon', karyesh, positions)
            
            if moon_lag and moon_kar:
                report['Verdict'] = "POSSIBLE WITH HELP"
                report['Reason'] = "There is no direct connection, but the Moon acts as a bridge. Success can happen through a third party, middleman, or sudden change of mind."
                report['Yoga'] = "Nakta Yoga (Translation of Light)"
            else:
                report['Verdict'] = "NO / UNLIKELY"
                report['Reason'] = "There is no direct connection between you and the objective right now. Things remain isolated."
                report['Yoga'] = "No Yoga (Void)"
        else:
            report['Verdict'] = "NO / UNLIKELY"
            report['Reason'] = "There is no connection and no middleman to assist. The matter is currently out of reach."
            report['Yoga'] = "No Yoga"

    return report

def get_moon_health(positions):
    moon = positions['Moon']
    sun_lon = positions['Sun']['Longitude']
    dist = abs(moon['Longitude'] - sun_lon)
    if dist > 180: dist = 360 - dist
    
    if dist < 12:
        return "⚠️ The Moon (Mind/Situation) is Combust (Amavasya). The situation is highly stressful, hidden, or lacking energy."
    elif moon['Sign'] in ['Scorpio']:
        return "⚠️ The Moon is Debilitated. Emotional anxiety or a weak foundation is affecting the query."
    return "The Moon (representing the mind and flow of events) is functioning normally."

# ==========================================
# 5. STREAMLIT USER INTERFACE
# ==========================================
def main():
    st.title("🕉️ Ultimate Prashna Kundali Engine")
    st.markdown("Advanced Horary Astrology featuring Tajika Yogas, Modality Timing, Retrograde analysis, and Translation of Light.")
    
    col1, col2 = st.columns([1, 2.5])
    
    with col1:
        st.header("1. Your Question")
        user_query = st.text_area(
            "What is your question?", 
            placeholder="E.g., Will I get the new job? Will it rain today? Will my ex return? Is the lost item safe?",
            help="Type naturally. The NLP engine maps your intent to the correct astronomical house."
        )
        
        st.markdown("---")
        
        st.subheader("2. Location")
        loc_choice = st.selectbox("Select City", list(CITY_DB.keys()))
        
        lat, lon = CITY_DB["Jaipur, Rajasthan (Default)"]["lat"], CITY_DB["Jaipur, Rajasthan (Default)"]["lon"]
        
        if loc_choice == "Custom Search...":
            custom_city = st.text_input("Enter City, State, Country")
            if custom_city:
                clat, clon = geocode_location(custom_city)
                if clat and clon:
                    lat, lon = clat, clon
                else:
                    st.error("Location not found.")
        elif loc_choice != "Jaipur, Rajasthan (Default)":
            lat, lon = CITY_DB[loc_choice]["lat"], CITY_DB[loc_choice]["lon"]
            
        st.subheader("3. Time of Query")
        ist_now = datetime.now(pytz.timezone('Asia/Kolkata'))
        q_date = st.date_input("Date", ist_now.date())
        q_time = st.time_input("Time", ist_now.time())
        
        generate = st.button("🔮 Ask the Cosmos", type="primary", use_container_width=True)

    if generate and user_query:
        with st.spinner("Analyzing astrological modalities, yogas, and planetary speeds..."):
            
            target_house, detected_word = extract_target_house(user_query)
            
            dt_combined = datetime.combine(q_date, q_time)
            ist_tz = pytz.timezone('Asia/Kolkata')
            dt_aware = ist_tz.localize(dt_combined)
            
            jd, tz_str = get_julian_day(dt_aware, lat, lon)
            positions, asc_deg = calculate_chart(jd, lat, lon)
            
            asc_sign_idx = int(asc_deg // 30)
            lagnesh = RASHI_LORDS[asc_sign_idx]
            karyesha_sign_idx = (asc_sign_idx + target_house - 1) % 12
            karyesh = RASHI_LORDS[karyesha_sign_idx]
            
            # Run the deep rules engine
            report = evaluate_horary_depth(positions, lagnesh, karyesh, target_house)
            moon_status = get_moon_health(positions)
            
            with col2:
                st.header("The Answer")
                st.info(f"🧠 **Engine detected:** You are asking about **'{detected_word}'**, mapping to **House {target_house}**.")
                
                # Dynamic Styling based on Verdict
                if "YES" in report['Verdict']:
                    st.success(f"### Outcome: {report['Verdict']}")
                elif "NO" in report['Verdict']:
                    st.error(f"### Outcome: {report['Verdict']}")
                else:
                    st.warning(f"### Outcome: {report['Verdict']}")
                    
                st.write(f"**Astrological Reasoning:** {report['Reason']}")
                
                st.markdown("---")
                st.subheader("Deeper Insights (Timing & Context)")
                st.write(f"⏱️ **Pace of Outcome:** {report['Timing']}")
                st.write(f"🔄 **Retrograde Factor:** {report['Retrograde']}")
                st.write(f"🌘 **The Mind/Environment (Moon):** {moon_status}")
                
                with st.expander("Show Raw Astrological Data"):
                    st.write(f"**Asker's Planet (Lagnesh):** {lagnesh}")
                    st.write(f"**Objective's Planet (Karyesh):** {karyesh}")
                    st.write(f"**Primary Yoga Formed:** {report['Yoga']}")
                    
                    df = pd.DataFrame.from_dict(positions, orient='index')
                    df['Longitude'] = df['Longitude'].apply(lambda x: f"{x:.2f}°")
                    df['Speed'] = df['Speed'].apply(lambda x: f"{x:.3f}")
                    df['Retrograde'] = df['Retrograde'].apply(lambda x: "Yes" if x else "No")
                    # Displaying relevant columns for a cleaner look
                    st.dataframe(df[['Sign', 'Modality', 'Degree', 'Retrograde', 'Speed']], use_container_width=True)

    elif generate and not user_query:
        st.error("Please type your question first!")

if __name__ == "__main__":
    main()
