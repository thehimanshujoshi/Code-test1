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
st.set_page_config(page_title="Pro Prashna Kundali", layout="wide", page_icon="🕉️")

# Swiss Ephemeris configuration (Lahiri Ayanamsha)
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
# 2. NATURAL LANGUAGE PROCESSING (NLP) ENGINE
# ==========================================
def extract_target_house(query):
    """Scans user's natural language query and maps it to the correct astrological house."""
    query = query.lower()
    
    # Extensive dictionary mapping real-world words to astrological houses
    house_keywords = {
        1: ['myself', 'health', 'life', 'appearance', 'body', 'me', 'i ', 'my '],
        2: ['money', 'wealth', 'salary', 'bank', 'finance', 'speech', 'family', 'saving', 'jewelry'],
        3: ['brother', 'sister', 'sibling', 'trip', 'travel', 'neighbor', 'email', 'message', 'courage', 'interview'],
        4: ['mother', 'house', 'home', 'real estate', 'property', 'car', 'vehicle', 'land', 'buying a home'],
        5: ['child', 'baby', 'son', 'daughter', 'exam', 'lottery', 'romance', 'love', 'dating', 'stock', 'crypto', 'pregnancy'],
        6: ['disease', 'sick', 'illness', 'pet', 'dog', 'cat', 'enemy', 'court', 'debt', 'loan', 'surgery', 'tenant', 'competition'],
        7: ['marriage', 'husband', 'wife', 'partner', 'business partner', 'divorce', 'relationship', 'spouse', 'contract'],
        8: ['death', 'inheritance', 'occult', 'sudden', 'accident', 'surgery', 'tax', 'insurance', 'alimony', 'mystery'],
        9: ['university', 'college', 'visa', 'abroad', 'religion', 'father', 'guru', 'long trip', 'pilgrimage', 'luck', 'master'],
        10: ['job', 'career', 'promotion', 'boss', 'government', 'profession', 'status', 'business', 'fame', 'company'],
        11: ['friend', 'profit', 'gain', 'desire', 'wish', 'elder brother', 'elder sister', 'income', 'network'],
        12: ['hospital', 'jail', 'prison', 'loss', 'foreign', 'hidden enemy', 'sleep', 'spiritual', 'ashram', 'expense']
    }
    
    for house, keywords in house_keywords.items():
        for keyword in keywords:
            # Using regex to find whole words to prevent partial matches
            if re.search(r'\b' + re.escape(keyword) + r'\b', query):
                return house, keyword
                
    # Default to 1st house (general query) if no matches found
    return 1, "general/self"

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
    
    # If the datetime is naive, localize it to the resolved timezone
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
        
        positions[p_name] = {
            'Longitude': lon_deg,
            'Latitude': lat_deg,
            'Sign': ZODIAC_SIGNS[sign_idx],
            'Sign_Idx': sign_idx,
            'Degree': lon_deg % 30,
            'Speed': speed,
            'Retrograde': 'Yes' if speed < 0 else 'No'
        }
        
    cusps, ascmc = swe.houses_ex(jd, lat, lon, b'W', flag)
    asc_deg = ascmc[0]
    return positions, asc_deg

def calculate_tithi(sun_lon, moon_lon):
    diff = (moon_lon - sun_lon) % 360
    tithi_num = math.floor(diff / 12) + 1
    paksha = "Shukla" if tithi_num <= 15 else "Krishna"
    display_num = tithi_num if tithi_num <= 15 else tithi_num - 15
    return f"{paksha} Paksha, Tithi {display_num} ({'Auspicious' if tithi_num not in [4,9,14] else 'Rikta/Empty - Obstacles likely'})"

# ==========================================
# 4. ADVANCED PRASHNA RULES ENGINE
# ==========================================
def evaluate_tajika_yogas(positions, lagnesh, karyesh):
    if lagnesh == karyesh:
        return "You are in complete control of the situation. The outcome is highly favorable.", "Self-Signification"
        
    p1, p2 = positions[lagnesh], positions[karyesh]
    orb1, orb2 = PLANET_ORBS[lagnesh], PLANET_ORBS[karyesh]
    avg_orb = (orb1 + orb2) / 2.0
    
    angle = abs(p1['Longitude'] - p2['Longitude'])
    if angle > 180:
        angle = 360 - angle
        
    aspects = {0: 'Conjunction', 60: 'Sextile', 90: 'Square', 120: 'Trine', 180: 'Opposition'}
    
    for asp_deg, asp_name in aspects.items():
        if abs(angle - asp_deg) <= avg_orb:
            fast_p, slow_p = (p1, p2) if abs(p1['Speed']) > abs(p2['Speed']) else (p2, p1)
            if fast_p['Degree'] < slow_p['Degree']:
                return f"Things are coming together. The necessary connection is being made for success.", f"Ithasala ({asp_name})"
            else:
                return f"The opportunity has recently passed, or there is an active separation/delay happening.", f"Easarpha ({asp_name})"
                
    return "There is no direct connection right now. Success is unlikely without a third party intervening.", "None"

def analyze_combustion_and_war(positions, lagnesh, karyesh):
    issues = []
    sun_lon = positions['Sun']['Longitude']
    
    for p in [lagnesh, karyesh]:
        if p != 'Sun' and p not in ['Rahu', 'Ketu']:
            dist = abs(positions[p]['Longitude'] - sun_lon)
            if dist > 180: dist = 360 - dist
            if dist <= 8.0:
                issues.append(f"⚠️ {p} is 'Combust' (too close to the Sun). Meaning this matter is hidden, restricted, or someone feels burnt out.")
                
    if lagnesh not in ['Sun', 'Moon', 'Rahu', 'Ketu'] and karyesh not in ['Sun', 'Moon', 'Rahu', 'Ketu']:
        dist = abs(positions[lagnesh]['Longitude'] - positions[karyesh]['Longitude'])
        if dist <= 1.0:
            winner = lagnesh if abs(positions[lagnesh]['Latitude']) > abs(positions[karyesh]['Latitude']) else karyesh
            issues.append(f"⚔️ There is an active conflict (Planetary War). Ultimately, {winner} has the upper hand mathematically.")
            
    return issues

# ==========================================
# 5. STREAMLIT USER INTERFACE
# ==========================================
def main():
    st.title("🕉️ AI-Powered Horary (Prashna) Engine")
    st.markdown("Simply ask your question naturally. The engine will detect the subject and calculate the exact astronomical outcome.")
    
    col1, col2 = st.columns([1, 2.5])
    
    with col1:
        st.header("1. Your Question")
        
        # SMART QUERY MODULE
        user_query = st.text_area(
            "What is your question?", 
            placeholder="E.g., Will I get the new job? Will my dog recover? Should I buy this house?",
            help="You can type or click the microphone icon on your mobile/desktop keyboard to dictate your question naturally."
        )
        
        st.markdown("---")
        
        # LOCATION MODULE
        st.subheader("2. Where are you?")
        loc_choice = st.selectbox("Select City", list(CITY_DB.keys()))
        
        lat, lon = CITY_DB["Jaipur, Rajasthan (Default)"]["lat"], CITY_DB["Jaipur, Rajasthan (Default)"]["lon"]
        
        if loc_choice == "Custom Search...":
            custom_city = st.text_input("Enter City, State, Country")
            if custom_city:
                clat, clon = geocode_location(custom_city)
                if clat and clon:
                    lat, lon = clat, clon
                    st.success(f"Located: {lat:.4f}, {lon:.4f}")
                else:
                    st.error("Location not found. Please try again.")
        elif loc_choice != "Jaipur, Rajasthan (Default)":
            lat, lon = CITY_DB[loc_choice]["lat"], CITY_DB[loc_choice]["lon"]
            
        # TIME MODULE (Fixed for local time)
        st.subheader("3. Time of Query")
        ist_now = datetime.now(pytz.timezone('Asia/Kolkata'))
        
        q_date = st.date_input("Date", ist_now.date())
        q_time = st.time_input("Time", ist_now.time())
        
        generate = st.button("🔮 Ask the Cosmos", type="primary", use_container_width=True)

    if generate and user_query:
        with st.spinner("Analyzing your question and calculating planetary positions..."):
            
            # NLP Step: Find out what they are asking about
            target_house, detected_word = extract_target_house(user_query)
            
            # Time & Astro Step
            dt_combined = datetime.combine(q_date, q_time)
            # Make the combined datetime aware of the IST timezone for the calculation
            ist_tz = pytz.timezone('Asia/Kolkata')
            dt_aware = ist_tz.localize(dt_combined)
            
            jd, tz_str = get_julian_day(dt_aware, lat, lon)
            positions, asc_deg = calculate_chart(jd, lat, lon)
            
            asc_sign_idx = int(asc_deg // 30)
            lagnesh = RASHI_LORDS[asc_sign_idx]
            karyesha_sign_idx = (asc_sign_idx + target_house - 1) % 12
            karyesh = RASHI_LORDS[karyesha_sign_idx]
            
            tithi_str = calculate_tithi(positions['Sun']['Longitude'], positions['Moon']['Longitude'])
            verdict, yoga_name = evaluate_tajika_yogas(positions, lagnesh, karyesh)
            dignity_issues = analyze_combustion_and_war(positions, lagnesh, karyesh)
            
            # --- DISPLAY DASHBOARD ---
            with col2:
                st.header("The Answer")
                
                # Show what the AI understood
                st.info(f"🧠 **Engine detected:** You are asking about **'{detected_word}'**, which is ruled by Astrological House **{target_house}**.")
                
                # Simplified User Verdict
                if "Success" in verdict or "control" in verdict:
                    st.success("✅ **YES / HIGHLY FAVORABLE**")
                    st.write(f"**The Astrological Reason:** {verdict}")
                elif "Passed" in verdict or "unlikely" in verdict:
                    st.error("❌ **NO / UNFAVORABLE / DELAYED**")
                    st.write(f"**The Astrological Reason:** {verdict}")
                else:
                    st.warning("⏳ **NEUTRAL / NEEDS INTERVENTION**")
                    st.write(f"**The Astrological Reason:** {verdict}")
                    
                if dignity_issues:
                    st.write("---")
                    st.write("### ⚠️ Potential Obstacles Identified:")
                    for issue in dignity_issues:
                        st.error(issue)
                        
                # Keep the deep math hidden in an expander for advanced users
                with st.expander("Show Advanced Astrological Calculations"):
                    st.write(f"**Panchang Matrix:** {tithi_str}")
                    st.write(f"**Ascendant (Lagna):** {ZODIAC_SIGNS[asc_sign_idx]} ({asc_deg%30:.2f}°)")
                    st.write(f"**Asker's Planet (Lagnesh):** {lagnesh}")
                    st.write(f"**Objective's Planet (Karyesh):** {karyesh}")
                    st.write(f"**Yoga Formed:** {yoga_name}")
                    
                    st.write("**Planetary Positions:**")
                    df = pd.DataFrame.from_dict(positions, orient='index')
                    df['Longitude'] = df['Longitude'].apply(lambda x: f"{x:.4f}°")
                    df['Latitude'] = df['Latitude'].apply(lambda x: f"{x:.4f}°")
                    df['Degree'] = df['Degree'].apply(lambda x: f"{x:.2f}°")
                    df['Speed'] = df['Speed'].apply(lambda x: f"{x:.4f}")
                    st.dataframe(df, use_container_width=True)

    elif generate and not user_query:
        st.error("Please type or speak your question first!")

if __name__ == "__main__":
    main()
