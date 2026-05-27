import streamlit as st
import swisseph as swe
import pandas as pd
import re
from datetime import datetime
import pytz
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ==========================================
# 1. CONFIGURATION & ASTRO CONSTANTS
# ==========================================
st.set_page_config(page_title="Advanced ML Prashna Engine", layout="wide", page_icon="⚡")
swe.set_sid_mode(swe.SIDM_LAHIRI)

PLANETS = {0: 'Sun', 1: 'Moon', 2: 'Mercury', 3: 'Venus', 4: 'Mars', 5: 'Jupiter', 6: 'Saturn', 10: 'Rahu', 11: 'Ketu'}
ZODIAC_SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
RASHI_LORDS = {0: 'Mars', 1: 'Venus', 2: 'Mercury', 3: 'Moon', 4: 'Sun', 5: 'Mercury', 6: 'Venus', 7: 'Mars', 8: 'Jupiter', 9: 'Saturn', 10: 'Saturn', 11: 'Jupiter'}
PLANET_ORBS = {'Sun': 15.0, 'Moon': 12.0, 'Mars': 8.0, 'Mercury': 7.0, 'Jupiter': 9.0, 'Venus': 7.0, 'Saturn': 9.0, 'Rahu': 0.0, 'Ketu': 0.0}

# Astrological Directions (Based on Elements)
DIRECTIONS = {
    "Aries": "East", "Leo": "East", "Sagittarius": "East",
    "Taurus": "South", "Virgo": "South", "Capricorn": "South",
    "Gemini": "West", "Libra": "West", "Aquarius": "West",
    "Cancer": "North", "Scorpio": "North", "Pisces": "North"
}

CITY_DB = {
    "Jaipur, Rajasthan (Default)": {"lat": 26.9124, "lon": 75.7873},
    "New Delhi, Delhi": {"lat": 28.6139, "lon": 77.2090},
    "Mumbai, Maharashtra": {"lat": 19.0760, "lon": 72.8777},
    "Bangalore, Karnataka": {"lat": 12.9716, "lon": 77.5946},
    "Custom Search...": None
}

# ==========================================
# 2. LOCAL MACHINE LEARNING ENGINE
# ==========================================
CORPUS_MAP = {
    "Battle": {"house": 7, "text": "win won match game versus beat team play tournament election fight compete winner lose loser victory defeat score championship trophy"},
    1: {"house": 1, "text": "myself health life appearance body recover safe danger survive me i physical well being mental state"},
    2: {"house": 2, "text": "money wealth salary bank finance speech family saving jewelry gold buy sell price expensive cheap income assets"},
    3: {"house": 3, "text": "brother sister sibling trip travel neighbor email message courage interview document contract news paper sign writing"},
    4: {"house": 4, "text": "mother house home real estate property car vehicle land rain weather storm climate stolen lost found missing underwear keys wallet phone search where is"},
    5: {"house": 5, "text": "child baby son daughter exam lottery romance love date dating stock crypto pregnancy play fun hobby creative"},
    6: {"house": 6, "text": "disease sick illness pet dog cat enemy court debt loan surgery tenant competition lawsuit dispute medicine doctor"},
    7: {"house": 7, "text": "marriage husband wife partner business divorce relationship spouse deal agreement thief lawyer open enemy cooperate"},
    8: {"house": 8, "text": "death inheritance occult sudden accident tax insurance alimony mystery secret bankruptcy hidden fear danger"},
    9: {"house": 9, "text": "university college visa abroad religion father guru long trip pilgrimage luck master astrology publish faith belief"},
    10: {"house": 10, "text": "job career promotion boss government profession status fame company judge authority hire fire work manager"},
    11: {"house": 11, "text": "friend profit gain desire wish elder income network award bonus success hope group organization"},
    12: {"house": 12, "text": "hospital jail prison loss foreign hidden enemy sleep spiritual ashram expense charity quit isolated alone"}
}

keys = list(CORPUS_MAP.keys())
documents = [CORPUS_MAP[k]["text"] for k in keys]
vectorizer = TfidfVectorizer(stop_words='english')
doc_vectors = vectorizer.fit_transform(documents)

def extract_intent_ml(query):
    query_vec = vectorizer.transform([query.lower()])
    similarities = cosine_similarity(query_vec, doc_vectors)[0]
    best_match_idx = similarities.argmax()
    best_score = similarities[best_match_idx]
    
    if best_score > 0.05:
        matched_key = keys[best_match_idx]
        target_house = CORPUS_MAP[matched_key]["house"]
        mode = "Battle" if matched_key == "Battle" else "Standard"
        reasoning = f"Semantic Match Score: {best_score:.2f} (Aligned with Vector Context: {matched_key})"
        return target_house, mode, reasoning
    return 1, "Standard", "Low semantic match. Defaulting to 1st House (General/Self)."

# ==========================================
# 3. CORE ASTRONOMICAL & VARGA CALCULATIONS
# ==========================================
def get_d9_sign(degree):
    """Calculates Navamsha (D9) Sign."""
    sign = int(degree / 30)
    deg_in_sign = degree % 30
    nav_idx = int(deg_in_sign / (30/9))
    sign_type = sign % 3 
    if sign_type == 0: start_sign = sign
    elif sign_type == 1: start_sign = (sign + 8) % 12
    else: start_sign = (sign + 4) % 12
    return ZODIAC_SIGNS[(start_sign + nav_idx) % 12]

def get_d3_sign(degree):
    """Calculates Drekkana (D3) Sign for Lost Items."""
    sign = int(degree / 30)
    deg_in_sign = degree % 30
    drek_idx = int(deg_in_sign / 10)
    if drek_idx == 0: return ZODIAC_SIGNS[sign]
    elif drek_idx == 1: return ZODIAC_SIGNS[(sign + 4) % 12]
    else: return ZODIAC_SIGNS[(sign + 8) % 12]

@st.cache_data(ttl=3600)
def geocode_location(city_name):
    try:
        geolocator = Nominatim(user_agent="prashna_ml_engine_final")
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
    # swe.FLG_SPEED added for exact planetary velocity
    flag = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
    for p_id, p_name in PLANETS.items():
        if p_id in [10, 11]:
            calc, _ = swe.calc_ut(jd, swe.TRUE_NODE, flag)
            if p_id == 11: calc = ((calc[0] + 180.0) % 360.0, 0, 0, 0, 0, 0)
        else:
            calc, _ = swe.calc_ut(jd, p_id, flag)
            
        sign_idx = int(calc[0] // 30)
        positions[p_name] = {
            'Longitude': calc[0], 
            'Sign': ZODIAC_SIGNS[sign_idx], 
            'Degree': calc[0] % 30, 
            'Speed': calc[3], 
            'Retrograde': calc[3] < 0,
            'D9_Sign': get_d9_sign(calc[0]),
            'D3_Sign': get_d3_sign(calc[0])
        }
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

    # TIE BREAKER RULE
    if score1 == score2:
        if abs(p1['Speed']) > abs(p2['Speed']):
            score1 += 0.5
        else:
            score2 += 0.5

    if score1 > score2: 
        return "TEAM 1 / FIRST OPTION WINS", "The 1st House Lord possesses mathematically superior velocity and dignity."
    elif score2 > score1: 
        return "TEAM 2 / SECOND OPTION WINS", "The opponent's 7th House Lord carries overwhelming forward momentum."
    return "TIE / EXTREMELY CLOSE MATCH", "Planetary strengths are gridlocked. Expect an unpredictable finish."

def evaluate_standard(positions, lagnesh, karyesh, target_house):
    report_extra = ""
    
    # Lost Item Logic (4th House)
    if target_house == 4:
        item_lord = positions[karyesh]
        d3_sign = item_lord['D3_Sign']
        direction = DIRECTIONS.get(d3_sign, "Unknown")
        report_extra = f"\n\n🧭 **Lost Item Radar:** The item is likely located in the **{direction}** direction. (Based on Drekkana/D3 analysis of the 4th Lord)."

    if lagnesh == karyesh: 
        return "YES / HIGHLY FAVORABLE", "Energies are self-signifying. You are in systemic control of this outcome." + report_extra
    
    has_aspect, asp_name = check_aspect(lagnesh, karyesh, positions)
    if has_aspect:
        p1, p2 = positions[lagnesh], positions[karyesh]
        fast_p, slow_p = (p1, p2) if abs(p1['Speed']) > abs(p2['Speed']) else (p2, p1)
        if fast_p['Degree'] < slow_p['Degree']: 
            return "YES / SUCCESS", "An applying cosmic connection indicates active manifestation." + report_extra
        return "NO / DELAYED", "The aspect configuration is separating. The prime window has shifted." + report_extra
        
    return "NO / UNFAVORABLE", "Zero aspectual connection exists between the querent and the objective." + report_extra

# ==========================================
# 5. STREAMLIT USER INTERFACE
# ==========================================
def main():
    st.title("⚡ Advanced ML Prashna Engine")
    st.markdown("Features local machine learning, D9/D3 Varga sub-charts, exact orbital speeds, and lost-item directional logic.")
    
    col1, col2 = st.columns([1, 2.5])
    
    with col1:
        st.header("1. Your Question")
        user_query = st.text_area("Ask anything naturally:", placeholder="Where are my lost keys? Who wins tonight? Will I get the job?")
        
        st.write("---")
        with st.expander("⚙️ Manual Override"):
            manual_override = st.selectbox(
                "Force Astrological House:",
                ["Auto-Detect via ML", "1: Self/Health", "2: Money", "3: Siblings/Messages", "4: Home/Lost items/Weather", "5: Romance/Exams", "6: Disease/Debt", "7: Competitions/Marriage", "8: Surgery/Inheritance", "9: Travel/Religion", "10: Career", "11: Gains/Friends", "12: Loss/Foreign"]
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
        
        generate = st.button("🔮 Calculate Matrix", type="primary", use_container_width=True)

    if generate and user_query:
        with st.spinner("Calculating Sub-Charts and ML Vectors..."):
            
            if manual_override != "Auto-Detect via ML":
                target_house = int(manual_override.split(":")[0])
                query_mode = "Battle" if target_house == 7 and "Competitions" in manual_override else "Standard"
                reasoning = "User bypassed ML. Manual selection active."
            else:
                target_house, query_mode, reasoning = extract_intent_ml(user_query)
            
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
                verdict, reason = evaluate_standard(positions, lagnesh, karyesh, target_house)
            
            with col2:
                st.header("The Answer")
                
                st.info("⚡ **ML Engine Log:** " + reasoning + "\n\n*Mapped Axis: House " + str(target_house) + " (" + query_mode + " Mode)*")
                
                if "YES" in verdict or "WINS" in verdict or "FAVORABLE" in verdict: 
                    st.success("### " + verdict)
                elif "NO" in verdict: 
                    st.error("### " + verdict)
                else: 
                    st.warning("### " + verdict)
                    
                st.write("**Astrological Breakdown:** " + reason)
                
                with st.expander("View Scientific Coordinates (Including D9 & D3)"):
                    st.write("**Ascendant (Lagna) Lord:** " + lagnesh)
                    st.write("**Objective House Lord:** " + karyesh)
                    df = pd.DataFrame.from_dict(positions, orient='index')
                    df['Longitude'] = df['Longitude'].apply(lambda x: f"{x:.2f}°")
                    df['Speed'] = df['Speed'].apply(lambda x: f"{x:.3f}°/day")
                    df['Retrograde'] = df['Retrograde'].apply(lambda x: "Yes" if x else "No")
                    st.dataframe(df[['Sign', 'Degree', 'Speed', 'Retrograde', 'D9_Sign', 'D3_Sign']], use_container_width=True)

    elif generate and not user_query:
        st.error("Please provide a query for the ML engine to evaluate.")

if __name__ == "__main__":
    main()
