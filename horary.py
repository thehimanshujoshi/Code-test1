import streamlit as st
import swisseph as swe
import pandas as pd
import re
from datetime import datetime
import pytz
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

# ==========================================
# 1. CONFIGURATION & ASTRO CONSTANTS
# ==========================================
st.set_page_config(page_title="Private Prashna Engine", layout="wide", page_icon="🔒")
swe.set_sid_mode(swe.SIDM_LAHIRI)

PLANETS = {0: 'Sun', 1: 'Moon', 2: 'Mercury', 3: 'Venus', 4: 'Mars', 5: 'Jupiter', 6: 'Saturn', 10: 'Rahu', 11: 'Ketu'}
ZODIAC_SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
RASHI_LORDS = {0: 'Mars', 1: 'Venus', 2: 'Mercury', 3: 'Moon', 4: 'Sun', 5: 'Mercury', 6: 'Venus', 7: 'Mars', 8: 'Jupiter', 9: 'Saturn', 10: 'Saturn', 11: 'Jupiter'}
PLANET_ORBS = {'Sun': 15.0, 'Moon': 12.0, 'Mars': 8.0, 'Mercury': 7.0, 'Jupiter': 9.0, 'Venus': 7.0, 'Saturn': 9.0, 'Rahu': 0.0, 'Ketu': 0.0}

CITY_DB = {
    "Jaipur, Rajasthan (Default)": {"lat": 26.9124, "lon": 75.7873},
    "New Delhi, Delhi": {"lat": 28.6139, "lon": 77.2090},
    "Mumbai, Maharashtra": {"lat": 19.0760, "lon": 72.8777},
    "Bangalore, Karnataka": {"lat": 12.9716, "lon": 77.5946},
    "Custom Search...": None
}

# ==========================================
# 2. 100% OFFLINE NLP KEYWORD ENGINE
# ==========================================
def extract_intent_offline(query):
    """
    Scans the query locally. No data leaves the server.
    """
    query = query.lower()
    
    # Check for Battle Mode first
    comp_keywords = ['win', 'won', 'match', 'game', 'vs', 'versus', 'beat', 'team', 'play', 'tournament', 'election', 'fight']
    if any(re.search(r'\b' + re.escape(kw) + r'\b', query) for kw in comp_keywords):
        return 7, "Battle", "Detected match/competition keywords."

    # Standard Dictionary
    house_keywords = {
        1: ['myself', 'health', 'life', 'appearance', 'body', 'recover', 'safe', 'danger', 'survive'],
        2: ['money', 'wealth', 'salary', 'bank', 'finance', 'speech', 'family', 'saving', 'jewelry', 'gold', 'buying', 'selling', 'price'],
        3: ['brother', 'sister', 'sibling', 'trip', 'travel', 'neighbor', 'email', 'message', 'courage', 'interview', 'document', 'contract', 'news'],
        4: ['mother', 'house', 'home', 'real estate', 'property', 'car', 'vehicle', 'land', 'rain', 'weather', 'storm', 'climate', 'stolen', 'lost', 'found', 'missing', 'underwear', 'keys', 'wallet', 'phone'],
        5: ['child', 'baby', 'son', 'daughter', 'exam', 'lottery', 'romance', 'love', 'date', 'dating', 'stock', 'crypto', 'pregnancy'],
        6: ['disease', 'sick', 'illness', 'pet', 'dog', 'cat', 'enemy', 'court', 'debt', 'loan', 'surgery', 'tenant', 'competition', 'lawsuit', 'dispute'],
        7: ['marriage', 'husband', 'wife', 'partner', 'business partner', 'divorce', 'relationship', 'spouse', 'deal', 'agreement', 'thief', 'lawyer'],
        8: ['death', 'inheritance', 'occult', 'sudden', 'accident', 'tax', 'insurance', 'alimony', 'mystery', 'secret', 'bankruptcy'],
        9: ['university', 'college', 'visa', 'abroad', 'religion', 'father', 'guru', 'long trip', 'pilgrimage', 'luck', 'master', 'astrology', 'publish'],
        10: ['job', 'career', 'promotion', 'boss', 'government', 'profession', 'status', 'business', 'fame', 'company', 'judge', 'authority', 'hire', 'fire'],
        11: ['friend', 'profit', 'gain', 'desire', 'wish', 'elder', 'income', 'network', 'award', 'bonus', 'success'],
        12: ['hospital', 'jail', 'prison', 'loss', 'foreign', 'hidden enemy', 'sleep', 'spiritual', 'ashram', 'expense', 'charity', 'quit']
    }
    
    for house, keywords in house_keywords.items():
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', query):
                return house, "Standard", f"Detected keyword: '{keyword}'"
                
    return 1, "Standard", "No specific keywords found. Defaulting to general query."

# ==========================================
# 3. CORE ASTRONOMICAL CALCULATIONS
# ==========================================
@st.cache_data(ttl=3600)
def geocode_location(city_name):
    try:
        geolocator = Nominatim(user_agent="prashna_offline_engine")
        location = geolocator.geocode(city_name)
        if location: return location.latitude, location.longitude
    except Exception:
        pass
    return None, None

def get_julian_day(dt, lat, lon):
    tf = TimezoneFinder()
    tz_str = tf.timezone_at(lng=lon, lat=lat) or "UTC"
    local_tz = pytz.timezone(tz_str)
    local_dt = local_tz.localize(dt) if dt.tzinfo is None else dt
    utc_dt = local_dt.astimezone(pytz.utc)
    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + utc_dt.minute/60.0 + utc_dt.second/3600.0)
    return jd, tz_str

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

    if score1 > score2: return "TEAM 1 / FIRST OPTION WINS", "The 1st House Lord holds more mathematical strength and speed compared to the opponent's lord."
    elif score2 > score1: return "TEAM 2 / SECOND OPTION WINS", "The 7th House Lord carries stronger astrological velocity and status right now than the 1st House Lord."
    return "TIE / EXTREMELY CLOSE MATCH", "Both structural planet significators share equal strength. Expect a down-to-the-wire finish."

def evaluate_standard(positions, lagnesh, karyesh):
    if lagnesh == karyesh: return "YES / HIGHLY FAVORABLE", "The energies are self-signifying and perfectly unified. The situation is under direct systemic control."
    has_aspect, asp_name = check_aspect(lagnesh, karyesh, positions)
    if has_aspect:
        p1, p2 = positions[lagnesh], positions[karyesh]
        fast_p, slow_p = (p1, p2) if abs(p1['Speed']) > abs(p2['Speed']) else (p2, p1)
        if fast_p['Degree'] < slow_p['Degree']: return "YES / SUCCESS", "Success is cleanly indicated through an applying cosmic aspect. Manifestation is in progress."
        return "NO / DELAYED", "The aspect configuration is separating, meaning the clear window of opportunity has stalled or shifted."
    return "NO / UNFAVORABLE", "There is no functional or aspectual connection joining the querent to the objective at this time."

# ==========================================
# 5. STREAMLIT USER INTERFACE
# ==========================================
def main():
    st.title("🔒 100% Private Prashna Engine")
    st.markdown("All queries are processed locally on this server. No data is sent to external AI APIs.")
    
    col1, col2 = st.columns([1, 2.5])
    
    with col1:
        st.header("1. Your Question")
        user_query = st.text_area("Type your question:", placeholder="Where are my keys? Will SRH win the match?")
        
        # Privacy Override Dropdown
        st.write("---")
        with st.expander("⚙️ Manual Topic Override (Optional)"):
            st.caption("If the local dictionary misses your keyword, you can force the topic here:")
            manual_override = st.selectbox(
                "Force Astrological House:",
                ["Auto-Detect", "1: Self/Health", "2: Money", "3: Siblings/Messages", "4: Home/Lost items/Weather", "5: Romance/Exams", "6: Disease/Debt", "7: Competitions/Marriage", "8: Surgery/Inheritance", "9: Travel/Religion", "10: Career", "11: Gains/Friends", "12: Loss/Foreign"]
            )
            
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
        with st.spinner("Processing locally..."):
            
            # Logic Routing (Auto vs Manual)
            if manual_override != "Auto-Detect":
                target_house = int(manual_override.split(":")[0])
                query_mode = "Battle" if target_house == 7 and "Competitions" in manual_override else "Standard"
                reasoning = "User manually selected the topic."
            else:
                target_house, query_mode, reasoning = extract_intent_offline(user_query)
            
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
                
                st.info("🔒 **Local Parse Result:** " + reasoning + "\n\n*Calculated Axis: House " + str(target_house) + " (" + query_mode + " Mode)*")
                
                if "YES" in verdict or "WINS" in verdict or "FAVORABLE" in verdict: 
                    st.success("### " + verdict)
                elif "NO" in verdict: 
                    st.error("### " + verdict)
                else: 
                    st.warning("### " + verdict)
                    
                st.write("**Astrological Breakdown:** " + reason)
                
                with st.expander("Show Scientific Planetary Coordinates"):
                    st.write("**Ascendant (Lagna) Lord:** " + lagnesh)
                    st.write("**Objective House Lord:** " + karyesh)
                    df = pd.DataFrame.from_dict(positions, orient='index')
                    df['Longitude'] = df['Longitude'].apply(lambda x: f"{x:.2f}°")
                    df['Speed'] = df['Speed'].apply(lambda x: f"{x:.3f}")
                    df['Retrograde'] = df['Retrograde'].apply(lambda x: "Yes" if x else "No")
                    st.dataframe(df[['Sign', 'Degree', 'Retrograde', 'Speed']], use_container_width=True)

    elif generate and not user_query:
        st.error("Please type out a query before querying the engine.")

if __name__ == "__main__":
    main()
