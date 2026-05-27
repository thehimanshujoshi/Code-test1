import streamlit as st
import swisseph as swe
import pandas as pd
from datetime import datetime
import pytz
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import google.generativeai as genai
import json

# ==========================================
# 1. AI "THINKING" CONFIGURATION
# ==========================================
# Get a free key from aistudio.google.com
genai.configure(api_key="YOUR_GEMINI_API_KEY") 
model = genai.GenerativeModel('gemini-1.5-flash')

def parse_intent_with_ai(user_query):
    """
    This is the brain. It reads the natural human question and preemptively 
    figures out exactly which astrological rules to apply.
    """
    prompt = f"""
    You are an expert Vedic Horary (Prashna) Astrologer. Analyze this user query: "{user_query}"
    
    1. Identify the 'Objective' of the query.
    2. Determine the corresponding Astrological House (1-12) for that objective.
        - 1: Health, Self
        - 2: Wealth, Family
        - 3: Siblings, Courage
        - 4: Property, Mother, Lost Items, Weather
        - 5: Children, Romance, Exams
        - 6: Disease, Pets, Debt, Enemies
        - 7: Marriage, Business Partnerships, Competitions, Opponents, Thieves
        - 8: Death, Occult, Inheritance
        - 9: Travel, Religion, Higher Ed
        - 10: Career, Status, Job
        - 11: Gains, Friends, Desires
        - 12: Loss, Jail, Foreign Lands
    3. Determine the 'Mode'. 
        - If the query is about a match, sports, election, fight, or direct competition between two sides, the Mode is "Battle" (comparing 1st House vs 7th House).
        - For everything else, the Mode is "Standard".
    
    Return ONLY a raw JSON object in this exact format:
    {{"target_house": 7, "mode": "Battle", "reasoning": "User is asking about a sports match. The opponent belongs to the 7th house."}}
    """
    try:
        response = model.generate_content(prompt)
        # Clean up the response to ensure it's pure JSON
        cleaned_text = response.text.replace('```json', '').replace('
```', '').strip()
        data = json.loads(cleaned_text)
        return data['target_house'], data['mode'], data['reasoning']
    except Exception as e:
        # Fallback if API fails
        return 1, "Standard", "AI Analysis failed, defaulting to 1st House."

# ==========================================
# 2. CONFIGURATION & CONSTANTS
# ==========================================
st.set_page_config(page_title="Sentient Prashna Engine", layout="wide", page_icon="🕉️")
swe.set_sid_mode(swe.SIDM_LAHIRI)

PLANETS = {0: 'Sun', 1: 'Moon', 2: 'Mercury', 3: 'Venus', 4: 'Mars', 5: 'Jupiter', 6: 'Saturn', 10: 'Rahu', 11: 'Ketu'}
ZODIAC_SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
RASHI_LORDS = {0: 'Mars', 1: 'Venus', 2: 'Mercury', 3: 'Moon', 4: 'Sun', 5: 'Mercury', 6: 'Venus', 7: 'Mars', 8: 'Jupiter', 9: 'Saturn', 10: 'Saturn', 11: 'Jupiter'}
PLANET_ORBS = {'Sun': 15.0, 'Moon': 12.0, 'Mars': 8.0, 'Mercury': 7.0, 'Jupiter': 9.0, 'Venus': 7.0, 'Saturn': 9.0, 'Rahu': 0.0, 'Ketu': 0.0}

CITY_DB = {
    "Jaipur, Rajasthan (Default)": {"lat": 26.9124, "lon": 75.7873},
    "New Delhi, Delhi": {"lat": 28.6139, "lon": 77.2090},
    "Mumbai, Maharashtra": {"lat": 19.0760, "lon": 72.8777},
    "Custom Search...": None
}

# ==========================================
# 3. CORE ASTRONOMICAL CALCULATIONS
# ==========================================
@st.cache_data(ttl=3600)
def geocode_location(city_name):
    geolocator = Nominatim(user_agent="prashna_sentient")
    location = geolocator.geocode(city_name)
    if location: return location.latitude, location.longitude
    return None, None

def get_julian_day(dt, lat, lon):
    tf = TimezoneFinder()
    tz_str = tf.timezone_at(lng=lon, lat=lat) or "UTC"
    local_tz = pytz.timezone(tz_str)
    if dt.tzinfo is None: local_dt = local_tz.localize(dt)
    else: local_dt = dt
    utc_dt = local_dt.astimezone(pytz.utc)
    return swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute/60.0 + utc_dt.second/3600.0), tz_str

def calculate_chart(jd, lat, lon):
    positions = {}
    flag = swe.FLG_SWIEPH | swe.FLG_SIDEREAL 
    for p_id, p_name in PLANETS.items():
        if p_id in [10, 11]:
            calc, _ = swe.calc_ut(jd, swe.TRUE_NODE, flag)
            if p_id == 11: calc = ((calc[0] + 180.0) % 360.0, 0, 0, 0, 0, 0)
        else:
            calc, _ = swe.calc_ut(jd, p_id, flag)
        sign_idx = int(calc[0] // 30)
        positions[p_name] = {'Longitude': calc[0], 'Sign': ZODIAC_SIGNS[sign_idx], 'Degree': calc[0] % 30, 'Speed': calc[3], 'Retrograde': calc[3] < 0}
    cusps, ascmc = swe.houses_ex(jd, lat, lon, b'W', flag)
    return positions, ascmc[0]

def check_aspect(p1, p2, positions):
    avg_orb = (PLANET_ORBS[p1] + PLANET_ORBS[p2]) / 2.0
    angle = abs(positions[p1]['Longitude'] - positions[p2]['Longitude'])
    if angle > 180: angle = 360 - angle
    aspects = {0: 'Conjunction', 60: 'Sextile', 90: 'Square', 120: 'Trine', 180: 'Opposition'}
    for asp_deg, asp_name in aspects.items():
        if abs(angle - asp_deg) <= avg_orb: return True, asp_name
    return False, None

# ==========================================
# 4. HORARY LOGIC ENGINE
# ==========================================
def evaluate_battle(positions, lagnesh, karyesh):
    p1, p2 = positions[lagnesh], positions[karyesh]
    score1, score2 = 0, 0
    if abs(p1['Speed']) > abs(p2['Speed']): score1 += 1
    else: score2 += 1
    if p1['Retrograde']: score1 -= 1
    if p2['Retrograde']: score2 -= 1
    if lagnesh in ['Jupiter', 'Venus', 'Sun']: score1 += 1
    if karyesh in ['Jupiter', 'Venus', 'Sun']: score2 += 1

    if score1 > score2: return "TEAM 1 / FAVORITE WINS", f"1st House Lord ({lagnesh}) is mathematically stronger than the Opponent's Lord ({karyesh})."
    elif score2 > score1: return "TEAM 2 / OPPONENT WINS", f"7th House Lord ({karyesh}) carries more momentum than the 1st House Lord ({lagnesh})."
    return "TIE / CLOSE MATCH", f"Both {lagnesh} and {karyesh} are locked in equal strength."

def evaluate_standard(positions, lagnesh, karyesh):
    if lagnesh == karyesh: return "YES", "Energies are perfectly aligned (Self-Signification)."
    has_aspect, asp_name = check_aspect(lagnesh, karyesh, positions)
    if has_aspect:
        fast_p, slow_p = (positions[lagnesh], positions[karyesh]) if abs(positions[lagnesh]['Speed']) > abs(positions[karyesh]['Speed']) else (positions[karyesh], positions[lagnesh])
        if fast_p['Degree'] < slow_p['Degree']: return "YES / SUCCESS", f"Success indicated via an applying connection ({asp_name})."
        return "NO / DELAYED", f"The opportunity is currently separating ({asp_name})."
    return "NO", "There is no direct connection between the asker and the objective."

# ==========================================
# 5. STREAMLIT USER INTERFACE
# ==========================================
def main():
    st.title("🧠 Sentient Prashna Engine")
    st.markdown("This engine uses AI to preemptively analyze the context of your question before doing the astrological math.")
    
    col1, col2 = st.columns([1, 2.5])
    
    with col1:
        st.header("1. Your Question")
        user_query = st.text_area("Ask anything naturally:", placeholder="Will my brother pass his exam? Where is my lost watch?")
        
        st.markdown("---")
        st.subheader("2. Location & Time")
        loc_choice = st.selectbox("Select City", list(CITY_DB.keys()))
        lat, lon = CITY_DB["Jaipur, Rajasthan (Default)"]["lat"], CITY_DB["Jaipur, Rajasthan (Default)"]["lon"]
        if loc_choice == "Custom Search...":
            custom_city = st.text_input("Enter City")
            if custom_city:
                clat, clon = geocode_location(custom_city)
                if clat and clon: lat, lon = clat, clon
        elif loc_choice != "Jaipur, Rajasthan (Default)":
            lat, lon = CITY_DB[loc_choice]["lat"], CITY_DB[loc_choice]["lon"]
            
        ist_now = datetime.now(pytz.timezone('Asia/Kolkata'))
        q_date = st.date_input("Date", ist_now.date())
        q_time = st.time_input("Time", ist_now.time())
        
        generate = st.button("🔮 Ask the Cosmos", type="primary", use_container_width=True)

    if generate and user_query:
        with st.spinner("AI is analyzing the context of your question..."):
            
            # 1. THE AI BRAIN PARSES THE INTENT PREEMPTIVELY
            target_house, query_mode, ai_reasoning = parse_intent_with_ai(user_query)
            
            # 2. EXECUTE THE MATH
            dt_combined = datetime.combine(q_date, q_time)
            dt_aware = pytz.timezone('Asia/Kolkata').localize(dt_combined)
            jd, tz_str = get_julian_day(dt_aware, lat, lon)
            positions, asc_deg = calculate_chart(jd, lat, lon)
            
            asc_sign_idx = int(asc_deg // 30)
            lagnesh = RASHI_LORDS[asc_sign_idx]
            karyesha_sign_idx = (asc_sign_idx + target_house - 1) % 12
            karyesh = RASHI_LORDS[karyesha_sign_idx]
            
            if query_mode == "Battle":
                verdict, reason = evaluate_battle(positions, lagnesh, karyesh)
            else:
                verdict, reason = evaluate_standard(positions, lagnesh, karyesh)
            
            with col2:
                st.header("The Answer")
                
                # Show the user that the AI actually understood them
                st.info(f"🧠 **AI Thought Process:** {ai_reasoning} \n\n*Mapping to Astrological House: {target_house}*")
                
                if "YES" in verdict or "WINS" in verdict: st.success(f"### {verdict}")
                elif "NO" in verdict: st.error(f"### {verdict}")
                else: st.warning(f"### {verdict}")
                    
                st.write(f"**Astrological Reasoning:** {reason}")

if __name__ == "__main__":
    main()
