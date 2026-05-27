import streamlit as st
import swisseph as swe
import pandas as pd
import math
from datetime import datetime
import pytz
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

# Deeptamsha (Orbs of Influence) in degrees per Tajika Prashna
PLANET_ORBS = {
    'Sun': 15.0, 'Moon': 12.0, 'Mars': 8.0, 'Mercury': 7.0,
    'Jupiter': 9.0, 'Venus': 7.0, 'Saturn': 9.0, 'Rahu': 0.0, 'Ketu': 0.0
}

# Pre-loaded Major Cities for fast loading
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
# 2. CORE ASTRONOMICAL CALCULATIONS
# ==========================================
@st.cache_data(ttl=3600)
def geocode_location(city_name):
    """Fetches exact decimal coordinates for a custom city search."""
    geolocator = Nominatim(user_agent="prashna_pro_engine")
    location = geolocator.geocode(city_name)
    if location:
        return location.latitude, location.longitude
    return None, None

def get_julian_day(dt, lat, lon):
    """Resolves precise timezone and calculates Julian Day."""
    tf = TimezoneFinder()
    tz_str = tf.timezone_at(lng=lon, lat=lat) or "UTC"
    local_tz = pytz.timezone(tz_str)
    local_dt = local_tz.localize(dt)
    utc_dt = local_dt.astimezone(pytz.utc)
    
    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, 
                    utc_dt.hour + utc_dt.minute/60.0 + utc_dt.second/3600.0)
    return jd, tz_str

def calculate_chart(jd, lat, lon):
    """Calculates pinpoint sidereal planetary longitudes, speeds, and latitudes."""
    positions = {}
    flag = swe.FLG_SWIEPH | swe.FLG_SIDEREAL 
    
    for p_id, p_name in PLANETS.items():
        if p_id == 10: # True Rahu
            calc, _ = swe.calc_ut(jd, swe.TRUE_NODE, flag)
        elif p_id == 11: # True Ketu
            calc_rahu, _ = swe.calc_ut(jd, swe.TRUE_NODE, flag)
            calc = ((calc_rahu[0] + 180.0) % 360.0, 0, 0, 0, 0, 0)
        else:
            calc, _ = swe.calc_ut(jd, p_id, flag)
            
        lon_deg = calc[0]
        lat_deg = calc[1] # Celestial latitude for Graha Yuddha
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
    """Calculates precise Lunar Day (Tithi)."""
    diff = (moon_lon - sun_lon) % 360
    tithi_num = math.floor(diff / 12) + 1
    paksha = "Shukla" if tithi_num <= 15 else "Krishna"
    display_num = tithi_num if tithi_num <= 15 else tithi_num - 15
    return f"{paksha} Paksha, Tithi {display_num} ({'Auspicious' if tithi_num not in [4,9,14] else 'Rikta/Empty - Obstacles likely'})"

def calc_saham(day_chart, point_a, point_b, asc_deg):
    """Calculates an Arabic Part / Saham mathematically."""
    saham_deg = (point_a - point_b + asc_deg) % 360
    # Tajika rule: If Asc is not between A and B, add 30 degrees
    # Simplified check for betweenness
    if not (min(point_b, point_a) <= asc_deg <= max(point_b, point_a)):
        saham_deg = (saham_deg + 30) % 360
    return saham_deg

# ==========================================
# 3. ADVANCED PRASHNA RULES ENGINE
# ==========================================
def evaluate_tajika_yogas(positions, lagnesh, karyesh):
    """Evaluates aspects based on exact average Deeptamsha (Orbs)."""
    if lagnesh == karyesh:
        return "Favorable: Lagnesh and Karyesh are the same planet.", "Self-Signification"
        
    p1, p2 = positions[lagnesh], positions[karyesh]
    orb1, orb2 = PLANET_ORBS[lagnesh], PLANET_ORBS[karyesh]
    avg_orb = (orb1 + orb2) / 2.0
    
    # Calculate angular distance
    angle = abs(p1['Longitude'] - p2['Longitude'])
    if angle > 180:
        angle = 360 - angle
        
    aspects = {0: 'Conjunction', 60: 'Sextile', 90: 'Square', 120: 'Trine', 180: 'Opposition'}
    
    for asp_deg, asp_name in aspects.items():
        if abs(angle - asp_deg) <= avg_orb:
            # Aspect exists! Determine Ithasala (Applying) or Easarpha (Separating)
            fast_p, slow_p = (p1, p2) if abs(p1['Speed']) > abs(p2['Speed']) else (p2, p1)
            
            # Using precise mathematical degree for the current sign
            if fast_p['Degree'] < slow_p['Degree']:
                return f"Success Indicated. Faster planet is applying to slower planet within orb ({avg_orb:.1f}°).", f"Ithasala ({asp_name})"
            else:
                return f"Opportunity Passed/Delayed. Faster planet is separating from slower planet.", f"Easarpha ({asp_name})"
                
    return "No direct aspect within exact orb limits. Success depends on intermediary (Nakta Yoga) or remedies.", "None"

def analyze_combustion_and_war(positions, lagnesh, karyesh):
    """Checks for Moudhya (Combustion) and Graha Yuddha (Planetary War)."""
    issues = []
    sun_lon = positions['Sun']['Longitude']
    
    # Combustion Check (Simplified < 8 degrees from Sun)
    for p in [lagnesh, karyesh]:
        if p != 'Sun' and p not in ['Rahu', 'Ketu']:
            dist = abs(positions[p]['Longitude'] - sun_lon)
            if dist > 180: dist = 360 - dist
            if dist <= 8.0:
                issues.append(f"⚠️ {p} is Combust (Moudhya). Its power to deliver is severely restricted.")
                
    # Graha Yuddha Check (Within 1 degree)
    if lagnesh not in ['Sun', 'Moon', 'Rahu', 'Ketu'] and karyesh not in ['Sun', 'Moon', 'Rahu', 'Ketu']:
        dist = abs(positions[lagnesh]['Longitude'] - positions[karyesh]['Longitude'])
        if dist <= 1.0:
            winner = lagnesh if abs(positions[lagnesh]['Latitude']) > abs(positions[karyesh]['Latitude']) else karyesh
            issues.append(f"⚔️ Planetary War (Graha Yuddha) between significators! {winner} wins mathematically based on celestial latitude.")
            
    return issues

# ==========================================
# 4. STREAMLIT USER INTERFACE
# ==========================================
def main():
    st.title("🕉️ Professional Horary (Prashna) Engine")
    st.markdown("Precision Tajika calculations using Swiss Ephemeris, True Nodes, and exact planetary Orbs.")
    
    col1, col2 = st.columns([1, 2.5])
    
    with col1:
        st.header("1. Chart Data")
        
        # LOCATION MODULE
        st.subheader("Location")
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
            
        # TIME MODULE
        st.subheader("Time of Query")
        q_date = st.date_input("Date", datetime.now())
        q_time = st.time_input("Time", datetime.now().time())
        
        # QUERY MODULE
        st.subheader("Objective")
        target_house = st.number_input("Target House (1-12) based on Query", min_value=1, max_value=12, value=1)
        
        generate = st.button("Cast Prashna Chart", type="primary", use_container_width=True)

    if generate:
        with st.spinner("Executing Astronomical Calculations..."):
            dt_combined = datetime.combine(q_date, q_time)
            jd, tz_str = get_julian_day(dt_combined, lat, lon)
            positions, asc_deg = calculate_chart(jd, lat, lon)
            
            # Fundamentals
            asc_sign_idx = int(asc_deg // 30)
            lagnesh = RASHI_LORDS[asc_sign_idx]
            karyesha_sign_idx = (asc_sign_idx + target_house - 1) % 12
            karyesh = RASHI_LORDS[karyesha_sign_idx]
            
            # Analytics
            tithi_str = calculate_tithi(positions['Sun']['Longitude'], positions['Moon']['Longitude'])
            verdict, yoga_name = evaluate_tajika_yogas(positions, lagnesh, karyesh)
            dignity_issues = analyze_combustion_and_war(positions, lagnesh, karyesh)
            
            # --- DISPLAY DASHBOARD ---
            with col2:
                st.header("Prashna Diagnostic Report")
                
                # Top Row Metrics
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Ascendant (Lagna)", f"{ZODIAC_SIGNS[asc_sign_idx]} ({asc_deg%30:.2f}°)")
                m2.metric("Lagnesh (Asker)", lagnesh)
                m3.metric("Karyesh (Query)", karyesh)
                m4.metric("Timezone Detected", tz_str)
                
                st.info(f"**Panchang Matrix:** {tithi_str}")
                
                # Analysis Result
                st.subheader("Tajika Yoga Verdict")
                if "Success" in verdict or "Favorable" in verdict:
                    st.success(f"**{yoga_name}**: {verdict}")
                elif "Passed" in verdict:
                    st.error(f"**{yoga_name}**: {verdict}")
                else:
                    st.warning(f"**{yoga_name}**: {verdict}")
                    
                if dignity_issues:
                    for issue in dignity_issues:
                        st.error(issue)
                        
                # Deep Data Table
                st.subheader("Exact Sidereal Coordinates")
                df = pd.DataFrame.from_dict(positions, orient='index')
                df['Longitude'] = df['Longitude'].apply(lambda x: f"{x:.4f}°")
                df['Latitude'] = df['Latitude'].apply(lambda x: f"{x:.4f}°")
                df['Degree'] = df['Degree'].apply(lambda x: f"{x:.2f}°")
                df['Speed'] = df['Speed'].apply(lambda x: f"{x:.4f}")
                st.dataframe(df, use_container_width=True)
                
                # Mathematical proofs expander
                with st.expander("Show Mathematical Proofs & Sahams"):
                    st.write("**Deeptamsha (Orb) Validation:**")
                    if lagnesh != karyesh:
                        avg_orb = (PLANET_ORBS[lagnesh] + PLANET_ORBS[karyesh]) / 2.0
                        dist = abs(positions[lagnesh]['Longitude'] - positions[karyesh]['Longitude'])
                        dist = min(dist, 360-dist)
                        st.code(f"Orb Limit: {avg_orb:.2f}° | Actual Distance: {dist:.2f}°")
                    
                    st.write("**Punya Saham (Point of Fortune):**")
                    day_chart = positions['Sun']['Longitude'] < 180 # simplified check
                    p_a = positions['Moon']['Longitude'] if day_chart else positions['Sun']['Longitude']
                    p_b = positions['Sun']['Longitude'] if day_chart else positions['Moon']['Longitude']
                    saham = calc_saham(day_chart, p_a, p_b, asc_deg)
                    s_sign = ZODIAC_SIGNS[int(saham // 30)]
                    st.code(f"Longitude: {saham:.4f}° | Sign: {s_sign} ({saham%30:.2f}°)")

if __name__ == "__main__":
    main()
