import streamlit as st
import swisseph as swe
import pandas as pd
from datetime import datetime
import pytz
from geopy.geocoders import Nominatim

# ==========================================
# 1. CONFIGURATION & SWISS EPHEMERIS SETUP
# ==========================================
st.set_page_config(page_title="Advanced Prashna Kundali", layout="wide")

# Set Ayanamsha to Lahiri (Chitra Paksha) for Vedic Calculations
swe.set_sid_mode(swe.SIDM_LAHIRI)

# Planetary Constants Mapping
PLANETS = {
    0: 'Sun', 1: 'Moon', 2: 'Mercury', 3: 'Venus', 
    4: 'Mars', 5: 'Jupiter', 6: 'Saturn', 
    10: 'Rahu', 11: 'Ketu' # Note: True Node calculations are used
}

ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", 
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

# Rashi Lords Mapping (0=Aries, 1=Taurus...)
RASHI_LORDS = {
    0: 'Mars', 1: 'Venus', 2: 'Mercury', 3: 'Moon', 4: 'Sun', 5: 'Mercury',
    6: 'Venus', 7: 'Mars', 8: 'Jupiter', 9: 'Saturn', 10: 'Saturn', 11: 'Jupiter'
}

# ==========================================
# 2. CORE ASTRONOMICAL CALCULATIONS
# ==========================================
def get_julian_day(dt, tz_str="UTC"):
    """Converts a local datetime to Julian Day for Swiss Ephemeris."""
    local_tz = pytz.timezone(tz_str)
    local_dt = local_tz.localize(dt)
    utc_dt = local_dt.astimezone(pytz.utc)
    
    # Calculate Julian Day
    jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, 
                    utc_dt.hour + utc_dt.minute/60.0 + utc_dt.second/3600.0)
    return jd

def calculate_chart(jd, lat, lon):
    """Calculates planetary positions, Lagna (Ascendant), and Bhavas (Houses)."""
    positions = {}
    
    # 1. Calculate Sidereal Planetary Positions
    for p_id, p_name in PLANETS.items():
        # Using SEFLG_SIDEREAL for Vedic astrology
        flag = swe.FLG_SWIEPH | swe.FLG_SIDEREAL 
        if p_id == 10: # Rahu (True Node)
            calc, _ = swe.calc_ut(jd, swe.TRUE_NODE, flag)
        elif p_id == 11: # Ketu (Opposite to Rahu)
            calc_rahu, _ = swe.calc_ut(jd, swe.TRUE_NODE, flag)
            calc = ((calc_rahu[0] + 180.0) % 360.0, 0, 0, 0, 0, 0)
        else:
            calc, _ = swe.calc_ut(jd, p_id, flag)
            
        lon_deg = calc[0]
        sign_idx = int(lon_deg // 30)
        
        positions[p_name] = {
            'Longitude': lon_deg,
            'Sign': ZODIAC_SIGNS[sign_idx],
            'Sign_Idx': sign_idx,
            'Degree': lon_deg % 30,
            'Retrograde': 'Yes' if calc[3] < 0 else 'No',
            'Speed': calc[3]
        }
        
    # 2. Calculate Ascendant (Lagna) & House Cusps (Placidus or Whole Sign)
    # 0 = Placidus, but Vedic often uses Whole Sign (W) or Sri Pati
    cusps, ascmc = swe.houses_ex(jd, lat, lon, b'W', flag)
    asc_deg = ascmc[0]
    asc_sign_idx = int(asc_deg // 30)
    
    return positions, asc_deg, asc_sign_idx

# ==========================================
# 3. PRASHNA (HORARY) RULES ENGINE
# ==========================================
def analyze_prashna(positions, asc_sign_idx, query_house):
    """
    Applies the detailed algorithm for Horary astrology.
    Analyzes Lagnesh (Querent) and Karyesh (Object of query).
    """
    # 1. Identify Significators
    lagnesh_planet = RASHI_LORDS[asc_sign_idx]
    
    karyesha_sign_idx = (asc_sign_idx + query_house - 1) % 12
    karyesha_planet = RASHI_LORDS[karyesha_sign_idx]
    
    lagnesh_data = positions.get(lagnesh_planet)
    karyesha_data = positions.get(karyesha_planet)
    moon_data = positions.get('Moon')
    
    analysis = {
        'Lagnesh (Asker)': lagnesh_planet,
        'Karyesh (Query)': karyesha_planet,
        'Moon (Mind)': f"{moon_data['Sign']} ({moon_data['Degree']:.2f}°)",
        'Tajika_Yoga': 'None',
        'Verdict': 'Neutral / Needs Deeper Analysis'
    }
    
    # 2. Evaluate Tajika Yogas (The Core of Prashna)
    # Check if Lagnesh and Karyesh are the same (Query belongs to self, e.g., health)
    if lagnesh_planet == karyesha_planet:
        analysis['Verdict'] = "Favorable: Lagnesh is also the Karyesh."
        return analysis

    # Calculate phase difference for Ithasala (Applying Aspect / Success) 
    # & Easarpha (Separating Aspect / Failure)
    speed_L = lagnesh_data['Speed']
    speed_K = karyesha_data['Speed']
    deg_L = lagnesh_data['Degree']
    deg_K = karyesha_data['Degree']
    
    # Simplified Aspect Check (Trine, Square, Sextile, Opposition, Conjunction)
    # *Note: A full app requires exact orb limits (Deeptamsha) per planet.
    angle = abs(lagnesh_data['Longitude'] - karyesha_data['Longitude'])
    aspects = {0: 'Conjunction', 60: 'Sextile', 90: 'Square', 120: 'Trine', 180: 'Opposition'}
    
    has_aspect = False
    for asp_deg, asp_name in aspects.items():
        if abs(angle - asp_deg) < 5 or abs(360 - angle - asp_deg) < 5: # 5 degree orb
            has_aspect = True
            
            # Fast planet must be behind slow planet for Ithasala (Success)
            fast_planet, slow_planet = (lagnesh_data, karyesha_data) if abs(speed_L) > abs(speed_K) else (karyesha_data, lagnesh_data)
            
            if fast_planet['Degree'] < slow_planet['Degree']:
                analysis['Tajika_Yoga'] = f'Ithasala ({asp_name})'
                analysis['Verdict'] = "Highly Favorable: Success is indicated."
            else:
                analysis['Tajika_Yoga'] = f'Easarpha ({asp_name})'
                analysis['Verdict'] = "Unfavorable: The opportunity has passed or is delayed."
            break
            
    if not has_aspect:
        # Check Nakta or Yamaya Yoga (Moon or slower planet transferring light)
        # *Placeholder for advanced logic*
        analysis['Verdict'] = "No direct connection between Asker and Objective. Success unlikely without intervention."

    return analysis

# ==========================================
# 4. STREAMLIT USER INTERFACE
# ==========================================
def main():
    st.title("🕉️ Advanced Prashna Kundali (Horary) Engine")
    st.markdown("""
    This application generates a Horary chart for the exact moment a query is asked and applies **Tajika Yogas** to determine the outcome.
    """)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.header("Query Details")
        q_date = st.date_input("Date of Question", datetime.now())
        q_time = st.time_input("Time of Question", datetime.now().time())
        city = st.text_input("City", "New Delhi, India")
        
        # Mapping common queries to Astrological Houses
        house_mapping = {
            "1st House: Health, Self, General wellbeing": 1,
            "2nd House: Wealth, Family, Speech": 2,
            "3rd House: Siblings, Short trips, Courage": 3,
            "4th House: Property, Mother, Vehicles": 4,
            "5th House: Children, Speculation, Romance": 5,
            "6th House: Disease, Enemies, Debt, Litigation": 6,
            "7th House: Marriage, Partnerships, Travel": 7,
            "8th House: Longevity, Hidden matters, Inheritance": 8,
            "9th House: Higher education, Religion, Long travel": 9,
            "10th House: Career, Profession, Status": 10,
            "11th House: Gains, Friends, Fulfillment of desires": 11,
            "12th House: Losses, Foreign lands, Imprisonment": 12
        }
        query_type = st.selectbox("Category of Question", list(house_mapping.keys()))
        target_house = house_mapping[query_type]
        
        generate = st.button("Cast Prashna Chart")

    if generate:
        with st.spinner("Calculating Ephemeris and Analyzing Yogas..."):
            try:
                # 1. Geocoding
                geolocator = Nominatim(user_agent="prashna_app")
                location = geolocator.geocode(city)
                if not location:
                    st.error("Location not found. Please enter a valid city.")
                    return
                    
                # 2. Time & JD Conversion
                dt_combined = datetime.combine(q_date, q_time)
                # Note: In a production app, use timezonefinder to get exact tz from lat/lon
                jd = get_julian_day(dt_combined, tz_str="Asia/Kolkata") 
                
                # 3. Calculation
                positions, asc_deg, asc_sign_idx = calculate_chart(jd, location.latitude, location.longitude)
                
                # 4. Analysis
                analysis = analyze_prashna(positions, asc_sign_idx, target_house)
                
                # --- DISPLAY RESULTS ---
                with col2:
                    st.header("Prashna Analysis Report")
                    
                    st.subheader("Fundamental Chart Details")
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Ascendant (Lagna)", ZODIAC_SIGNS[asc_sign_idx])
                    col_b.metric("Lagna Lord (Lagnesh)", analysis['Lagnesh (Asker)'])
                    col_c.metric("Query Lord (Karyesh)", analysis['Karyesh (Query)'])
                    
                    st.markdown("---")
                    
                    st.subheader("Planetary Positions")
                    df = pd.DataFrame.from_dict(positions, orient='index')
                    df['Longitude'] = df['Longitude'].apply(lambda x: f"{x:.2f}°")
                    df['Degree'] = df['Degree'].apply(lambda x: f"{x:.2f}°")
                    df['Speed'] = df['Speed'].apply(lambda x: f"{x:.4f}")
                    st.dataframe(df, use_container_width=True)
                    
                    st.markdown("---")
                    
                    st.subheader("Astrological Verdict")
                    if "Favorable" in analysis['Verdict']:
                        st.success(analysis['Verdict'])
                    elif "Unfavorable" in analysis['Verdict'] or "unlikely" in analysis['Verdict']:
                        st.error(analysis['Verdict'])
                    else:
                        st.warning(analysis['Verdict'])
                        
                    with st.expander("Detailed Algorithmic Reasoning"):
                        st.write(f"**Tajika Yoga Identified:** {analysis['Tajika_Yoga']}")
                        st.write(f"**Moon's Position:** {analysis['Moon (Mind)']} - The Moon represents the querent's mind and the immediate flow of events.")
                        st.write("*Note: In Prashna, a retrograde Karyesh often indicates that the subject matter will return or repeat, but with delays.*")

            except Exception as e:
                st.error(f"An error occurred during calculation: {e}")

if __name__ == "__main__":
    main()
