import streamlit as st
import pandas as pd
import random

# --- 1. SECURE DATA FETCHING ---
def get_data(sheet_name):
    sheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    df = pd.read_csv(url)
    # Clean up any trailing spaces in column names or data
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
        # Load Raw Data
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
            
            # 1. UI Selectors
            v_options = df_prefs_raw['VersionName'].unique()
            l_options = df_rooms_raw['Accommodation'].unique()
            
            col1, col2 = st.columns(2)
            version = col1.selectbox("Social Map Version", v_options)
            location = col2.selectbox("Location", l_options)

            # --- THE FIX: STEP-BY-STEP FILTERING ---
            # Filter first so we only have one row per person
            df_filtered = df_prefs_raw[df_prefs_raw['VersionName'] == version]
            
            # Ensure the Name column is clean
            df_filtered['Name'] = df_filtered['Name'].astype(str).str.strip()
            
            # Now safely turn into a dictionary
            people = df_filtered.set_index('Name').to_dict('index')
            
            # Filter rooms
            rooms = df_rooms_raw[df_rooms_raw['Accommodation'] == location].to_dict('records')
            
            # 2. History & Frustration Logic
            frustration = {name: 0 for name in people.keys()}
            past_roommates = {name: set() for name in people.keys()}
            
            if not df_hist.empty:
                for _, row in df_hist.iterrows():
                    p_name = str(row['PersonName']).strip()
                    if p_name in frustration:
                        if row['RoomQuality'] < 5:
                            frustration[p_name] += (10 - row['RoomQuality']) * 2
                        
                        # Track past roommates
                        others = df_hist[
                            (df_hist['Accommodation'] == row['Accommodation']) & 
                            (df_hist['RoomName'] == row['RoomName']) & 
                            (df_hist['PersonName'] != p_name)
                        ]['PersonName'].tolist()
                        past_roommates[p_name].update([str(n).strip() for n in others])

            # 3. Solver Button
            if st.button("🚀 Run Social Tetris"):
                names = list(people.keys())
                best_arr, best_score = None, -float('inf')
                
                # Check for capacity match
                total_cap = sum(r['Capacity'] for r in rooms)
                if total_cap < len(names):
                    st.error(f"Not enough beds! Need {len(names)}, only have {total_cap}.")
                    st.stop()

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
                            
                            # Strict No
                            s_no = [n.strip() for n in str(p['StrictNo']).split(',')] if pd.notna(p['StrictNo']) else []
                            if any(n in others for n in s_no): score -= 10**6
                            
                            # Tiers
                            t1 = [n.strip() for n in str(p['Tier1']).split(',')] if pd.notna(p['Tier1']) else []
                            t2 = [n.strip() for n in str(p['Tier2']).split(',')] if pd.notna(p['Tier2']) else []
                            
                            if any(n in others for n in t1): score += 100
                            for n in others:
                                if n in t2: score += 30
                            
                            # New People Variety
                            if p['NewPeople'] == True:
                                for roommate in others:
                                    if roommate in past_roommates[p_name] and roommate not in t1 and roommate not in t2:
                                        score -= 50 
                            
                            # Fairness
                            score += (r['Quality'] * 10) + (frustration[p_name] * 1.5)
                    
                    if score > best_score:
                        best_score, best_arr = score, temp_arr

                # Display Results
                st.success(f"Best fit found! (Score: {best_score})")
                for rm, folks in best_arr.items():
                    with st.expander(f"🏠 {rm}", expanded=True):
                        st.write(", ".join(folks))
                
                # Manual Entry Table
                h_rows = []
                for rm, folks in best_arr.items():
                    q = next(r['Quality'] for r in rooms if r['RoomName'] == rm)
                    for p in folks: h_rows.append([location, p, rm, q, version])
                st.table(pd.DataFrame(h_rows, columns=["Accommodation", "PersonName", "RoomName", "Quality", "Version"]))

        with tab_history:
            st.subheader("Fairness Ledger")
            st.bar_chart(pd.Series(frustration))
            st.write("**Past Roommates (Rotating targets):**")
            st.json({k: list(v) for k, v in past_roommates.items() if v})

    except Exception as e:
        st.error(f"Something is wrong in your Google Sheet format. Error: {e}")
