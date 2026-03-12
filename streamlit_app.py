import streamlit as st
import pandas as pd
import random

# --- 1. SECURE DATA FETCHING ---
def get_data(sheet_name):
    sheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    return df

# --- 2. LOGIN LOGIC ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    st.markdown("### 🔐 Secure Trip Access")
    pwd = st.text_input("Enter Trip Password", type="password")
    if st.button("Log In"):
        if pwd == st.secrets["password"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else: st.error("Incorrect password")
    return False

# --- 3. MAIN APP ---
if check_password():
    try:
        df_prefs_raw = get_data("Preferences")
        df_rooms_raw = get_data("Rooms")
        df_hist = get_data("History")
        
        tab_solve, tab_data, tab_history = st.tabs(["🎲 Solver", "📊 Live Data", "📜 Fairness Log"])

        with tab_data:
            st.subheader("Live Data from Google Sheets")
            st.dataframe(df_prefs_raw)
            st.dataframe(df_rooms_raw)

        with tab_solve:
            st.subheader("Generate Arrangement")
            
            v_options = df_prefs_raw['VersionName'].unique()
            l_options = df_rooms_raw['Accommodation'].unique()
            
            col1, col2 = st.columns(2)
            version = col1.selectbox("Social Map Version", v_options)
            location = col2.selectbox("Location", l_options)

            # Filtering & Cleaning
            df_filtered = df_prefs_raw[df_prefs_raw['VersionName'] == version].copy()
            df_filtered['Name'] = df_filtered['Name'].astype(str).str.strip()
            
            duplicate_names = df_filtered[df_filtered.duplicated(['Name'])]['Name'].tolist()
            if duplicate_names:
                st.error(f"🚨 Duplicate Name Detected: {', '.join(duplicate_names)}.")
                st.stop()
            
            people = df_filtered.set_index('Name').to_dict('index')
            rooms = df_rooms_raw[df_rooms_raw['Accommodation'] == location].to_dict('records')
            
            # History & Frustration Map
            frustration = {name: 0 for name in people.keys()}
            past_roommates = {name: set() for name in people.keys()}
            
            if not df_hist.empty:
                for _, row in df_hist.iterrows():
                    p_name = str(row['PersonName']).strip()
                    if p_name in frustration:
                        if row['RoomQuality'] < 5:
                            frustration[p_name] += (10 - row['RoomQuality']) * 2
                        others = df_hist[
                            (df_hist['Accommodation'] == row['Accommodation']) & 
                            (df_hist['RoomName'] == row['RoomName']) & 
                            (df_hist['PersonName'] != p_name)
                        ]['PersonName'].tolist()
                        past_roommates[p_name].update([str(n).strip() for n in others])

            if st.button("🚀 Run Social Tetris"):
                names = list(people.keys())
                best_arr, best_score = None, -float('inf')
                
                total_cap = sum(r['Capacity'] for r in rooms)
                if total_cap < len(names):
                    st.error(f"Not enough beds! Need {len(names)}, only have {total_cap}.")
                    st.stop()

                # --- ALGORITHM ---
                for i in range(2500):
                    random.shuffle(names)
                    temp_arr, idx, score = {}, 0, 0
                    for r in rooms:
                        occupants = names[idx : idx + r['Capacity']]
                        temp_arr[r['RoomName']] = occupants
                        idx += r['Capacity']
                        
                        for p_name in occupants:
                            p = people[p_name]
                            others = [n for n in occupants if n != p_name]
                            
                            s_no = [n.strip() for n in str(p['StrictNo']).split(',')] if pd.notna(p['StrictNo']) else []
                            if any(n in others for n in s_no): score -= 10**6
                            
                            t1 = [n.strip() for n in str(p['Tier1']).split(',')] if pd.notna(p['Tier1']) else []
                            t2 = [n.strip() for n in str(p['Tier2']).split(',')] if pd.notna(p['Tier2']) else []
                            
                            if any(n in others for n in t1): score += 100
                            for n in others:
                                if n in t2: score += 30
                            
                            # Gender Preference Logic
                            g_pref = str(p.get('GenderPref', '')).strip().lower()
                            my_gender = str(p.get('Gender', '')).strip().lower()
                            if g_pref in ['strict', 'prefer']:
                                illegal_genders = [n for n in others if str(people[n].get('Gender', '')).strip().lower() != my_gender and n
