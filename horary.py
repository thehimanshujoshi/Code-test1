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
st.set_page_config(page_title="Universal Prashna Engine", layout="wide", page_icon="🕉️")

swe.set_sid_mode(swe.SIDM_LAHIRI)

PLANETS = {0: 'Sun', 1: 'Moon', 2: 'Mercury', 3: 'Venus', 4: 'Mars', 5: 'Jupiter', 6: 'Saturn', 10: 'Rahu', 11: 'Ketu'}
ZODIAC_SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
RASHI_LORDS = {0: 'Mars', 1: 'Venus', 2: 'Mercury', 3: 'Moon', 4: 'Sun', 5: 'Mercury', 6: 'Venus', 7: 'Mars', 8: 'Jupiter', 9: 'Saturn', 10: 'Saturn', 11: 'Jupiter'}

PLANET_ORBS = {'Sun': 15.0, 'Moon': 12.0, 'Mars': 8.0, 'Mercury': 7.0, 'Jupiter': 9.0, 'Venus': 7.0, 'Saturn': 9.0, 'Rahu': 0.0, 'Ketu': 0.0}
MODALITIES = {"Aries": "Movable", "Taurus": "Fixed", "Gemini": "Dual", "Cancer": "Movable", "Leo": "Fixed", "Virgo": "Dual", "Libra": "Movable", "Scorpio": "Fixed", "Sagittarius": "Dual", "Capricorn": "Movable", "Aquarius": "Fixed", "Pisces": "Dual"}

CITY_DB = {
    "Jaipur, Rajasthan (Default)": {"lat": 26.9124, "lon": 75.7873},
    "New Delhi, Delhi": {"lat": 28.6139, "lon": 77.2090},
    "Mumbai, Maharashtra": {"lat": 19.0760, "lon": 72.8777},
    "Bangalore, Karnataka": {"lat": 12.9716, "lon": 77.5946},
    "Custom Search...": None
}

# ==========================================
# 2. UNIVERSAL NLP ENGINE
# ==========================================
def extract_intent(query):
    query = query.lower()
    
    # 1. Check if this is a competition / sports / election query
    comp_keywords = ['win', 'won', 'match', 'game', 'vs', 'versus', 'beat', 'team', 'play', 'tournament', 'election', 'fight']
    if any(re.search(r'\b' + re.escape(kw) + r'\b', query) for kw in comp_keywords):
        return 7, "Competition/Match", "Battle"

    # 2. Regular Horary Dictionary
    house_keywords = {
        1: ['myself', 'health', 'life', 'appearance', 'body', 'me', ' i ', ' my ', 'recover', 'safe', 'danger', 'survive'],
        2: ['money', 'wealth', 'salary', 'bank', 'finance', 'speech', 'family', 'saving', 'jewelry', 'gold', 'buying', 'selling', 'price'],
        3: ['brother', 'sister', 'sibling', 'trip', 'travel', 'neighbor', 'email', 'message', 'courage', 'interview', 'document', 'contract', 'news'],
        4: ['mother', 'house', 'home', 'real estate', 'property', 'car', 'vehicle', 'land', 'rain', 'weather', 'storm', 'climate', 'stolen', 'lost', 'found', 'missing'],
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
                return house, keyword, "Standard"
                
    return 1, "Unrecognized Topic", "Standard"

# ==========================================
# 3. CORE ASTRONOMICAL CALCULATIONS
# ==========================================
@st.cache_data(ttl=3600)
def geocode_location(city_name):
    geolocator = Nominatim(user_agent="prashna_universal")
    location = geolocator.geocode(city_name)
    if location:
        return location.latitude, location.longitude
    return None, None

def get_julian_day(dt, lat, lon):
    tf = TimezoneFinder()
    tz_str = tf.timezone_at(lng=lon, lat=lat) or "UTC"
    local_tz = pytz.timezone(tz_str)
    
    if dt.tzinfo is None: local_dt = local_tz.localize(dt)
    else: local_dt = dt
        
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
        positions[p_name] = {
            'Longitude': calc[0], 'Latitude': calc[1], 'Sign': ZODIAC_SIGNS[sign_idx],
            'Modality': MODALITIES[ZODIAC_SIGNS[sign_idx]], 'Degree': calc[0] % 30,
            'Speed': calc[3], 'Retrograde': calc[3] < 0
        }
        
    cusps, ascmc = swe.houses_ex(jd, lat, lon, b'W', flag)
    return positions, ascmc[0]

def check_aspect(p1, p2, positions):
    avg_orb = (PLANET_ORBS[p1] + PLANET_ORBS[p2]) / 2.0
    angle = abs(positions[p1]['Longitude'] - positions[p2]['Longitude'])
    if angle > 180: angle = 360 - angle
    
    aspects = {0: 'Conjunction', 60: 'Sextile', 90: 'Square', 120: 'Trine', 180: 'Opposition'}
    for asp_deg, asp_name in aspects.items():
        if abs(angle - asp_deg) <= avg_orb: return True, asp_name, avg_orb
    return False, None, None

# ==========================================
# 4. HORARY LOGIC (STANDARD VS COMPETITION)
# ==========================================
def evaluate_battle(positions, lagnesh, karyesh):
    """Specifically for Sports, Elections, and 'Who will win' queries."""
    report = {}
    
    # 1st House = Team 1 (Usually the team asked about first, or the home team)
    # 7th House = Team 2 (The opponent)
    p1 = positions[lagnesh]
    p2 = positions[karyesh]
    
    score1 = 0
    score2 = 0
    
    # Speed (Faster planet has more initiative/momentum)
    if abs(p1['Speed']) > abs(p2['Speed']): score1 += 1
    else: score2 += 1
        
    # Retrograde (Moving backward = losing ground)
    if p1['Retrograde']: score1 -= 1
    if p2['Retrograde']: score2 -= 1
        
    # Benefic Nature (Jupiter/Venus grant natural strength)
    if lagnesh in ['Jupiter', 'Venus', 'Sun']: score1 += 1
    if karyesh in ['Jupiter', 'Venus', 'Sun']: score2 += 1

    if score1 > score2:
        report['Verdict'] = "TEAM 1 / FIRST OPTION WINS"
        report['Reason'] = f"The 1st House Lord ({lagnesh}) is mathematically stronger, faster, or in better dignity than the opponent's 7th House Lord ({karyesh})."
    elif score2 > score1:
        report['Verdict'] = "TEAM 2 / SECOND OPTION WINS"
        report['Reason'] = f"The Opponent's 7th House Lord ({karyesh}) carries more momentum and strength than the 1st House Lord ({lagnesh})."
    else:
        report['Verdict'] = "TIE / EXTREMELY CLOSE MATCH"
        report['Reason'] = f"Both {lagnesh} and {karyesh} are locked in equal strength. The outcome will be determined in the final moments or go to a draw."
        
    return report

def evaluate_standard(positions, lagnesh, karyesh):
    report = {}
    if lagnesh == karyesh:
        report['Verdict'] = "YES / FAVORABLE"
        report['Reason'] = "The energies are perfectly aligned (Self-Signification). The situation is under your control."
        return report
        
    has_aspect, asp_name, orb = check_aspect(lagnesh, karyesh, positions)
    
    if has_aspect:
        p1, p2 = positions[lagnesh], positions[karyesh]
        fast_p, slow_p = (p1, p2) if abs(p1['Speed']) > abs(p2['Speed']) else (p2, p1)
        if fast_p['Degree'] < slow_p['Degree']:
            report['Verdict'] = "YES / SUCCESS"
            report['Reason'] = f"Success is indicated via a direct applying connection ({asp_name}). Things are coming together."
        else:
            report['Verdict'] = "NO / DELAYED"
            report['Reason'] = f"The opportunity has passed or is currently separating ({asp_name})."
    else:
        if lagnesh != 'Moon' and karyesh != 'Moon':
            moon_lag, _, _ = check_aspect('Moon', lagnesh, positions)
            moon_kar, _, _ = check_aspect('Moon', karyesh, positions)
            if moon_lag and moon_kar:
                report['Verdict'] = "POSSIBLE WITH HELP"
                report['Reason'] = "No direct connection, but the Moon acts as a bridge. Success requires a third party or middleman."
            else:
                report['Verdict'] = "NO / UNLIKELY"
                report['Reason'] = "There is no connection between you and the objective."
        else:
            report['Verdict'] = "NO / UNLIKELY"
            report['Reason'] = "The matter is currently out of reach with no connection."
    return report

# ==========================================
# 5. STREAMLIT USER INTERFACE
# ==========================================
def main():
    st.title("🕉️ Universal Prashna Engine")
    st.markdown("Ask anything: Health, wealth, lost items, or who will win tonight's match.")
    
    col1, col2 = st.columns([1, 2.5])
    
    with col1:
        st.header("1. Your Question")
        user_query = st.text_area("What is your question?", placeholder="Will Rajasthan Royals win? Will it rain? Where are my keys?")
        
        # Override Mechanism for absolute universality
        st.write("---")
        with st.expander("⚙️ Manual AI Override (Optional)"):
            st.caption("If the AI guesses your topic wrong, force the correct Astrological House here:")
            manual_override = st.selectbox(
                "Force House Calculation:",
                ["Auto-Detect (Recommended)", "1: Self/Health", "2: Money", "3: Siblings/Messages", "4: Home/Weather/Lost items", "5: Romance/Children/Exams", "6: Disease/Pets/Debt", "7: Competitions/Matches/Marriage", "8: Death/Surgery/Occult", "9: Travel/Visa/Religion", "10: Career/Job", "11: Gains/Friends", "12: Loss/Foreign"]
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
        with st.spinner("Analyzing astronomical positions..."):
            
            # Determine Intent & House
            ai_house, detected_word, query_mode = extract_intent(user_query)
            
            if manual_override != "Auto-Detect (Recommended)":
                target_house = int(manual_override.split(":")[0])
                query_mode = "Standard" if target_house != 7 else "Battle"
                detected_word = "Manual Override"
            else:
                target_house = ai_house

            # Astronomy Calculation
            dt_combined = datetime.combine(q_date, q_time)
            dt_aware = pytz.timezone('Asia/Kolkata').localize(dt_combined)
            jd, tz_str = get_julian_day(dt_aware, lat, lon)
            positions, asc_deg = calculate_chart(jd, lat, lon)
            
            asc_sign_idx = int(asc_deg // 30)
            lagnesh = RASHI_LORDS[asc_sign_idx]
            karyesha_sign_idx = (asc_sign_idx + target_house - 1) % 12
            karyesh = RASHI_LORDS[karyesha_sign_idx]
            
            # Route to Correct Logic
            if query_mode == "Battle":
                report = evaluate_battle(positions, lagnesh, karyesh)
            else:
                report = evaluate_standard(positions, lagnesh, karyesh)
            
            with col2:
                st.header("The Answer")
                if query_mode == "Battle":
                    st.info(f"⚔️ **Engine detected a Competition/Match.** Using 1st vs 7th House Battle Logic.")
                else:
                    st.info(f"🧠 **Engine detected:** You are asking about **'{detected_word}'**, mapping to **House {target_house}**.")
                
                # Display Outcome
                if "YES" in report['Verdict'] or "WINS" in report['Verdict']: st.success(f"### {report['Verdict']}")
                elif "NO" in report['Verdict']: st.error(f"### {report['Verdict']}")
                else: st.warning(f"### {report['Verdict']}")
                    
                st.write(f"**Astrological Reasoning:** {report['Reason']}")
                
                with st.expander("Show Raw Astrological Data"):
                    st.write(f"**Asker / Team 1 (Lagnesh):** {lagnesh}")
                    st.write(f"**Objective / Team 2 (Karyesh):** {karyesh}")
                    df = pd.DataFrame.from_dict(positions, orient='index')
                    df['Longitude'] = df['Longitude'].apply(lambda x: f"{x:.2f}°")
                    df['Speed'] = df['Speed'].apply(lambda x: f"{x:.3f}")
                    df['Retrograde'] = df['Retrograde'].apply(lambda x: "Yes" if x else "No")
                    st.dataframe(df[['Sign', 'Modality', 'Degree', 'Retrograde', 'Speed']], use_container_width=True)

if __name__ == "__main__":
    main()
