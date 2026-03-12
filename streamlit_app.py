import streamlit as st
import pandas as pd
import random

# --- 1. DATA FETCHING ---
def get_data(sheet_name):
    sheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    return pd.read_csv(url)

# --- 2. LOGIN ---
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
        df_prefs = get_data("Preferences")
        df_rooms = get_data("Rooms")
        df_hist = get_data("History")
        
        tab_solve, tab_data, tab_history = st.tabs(["🎲 Solver", "📊 Live Data", "📜 Fairness Log"])

        with tab_solve:
            st.subheader("Generate Arrangement")
            
            col1, col2 = st.columns(2)
            version = col1.selectbox("Social Map", df_prefs['VersionName'].unique())
            location = col2.selectbox("Location", df_rooms['Accommodation'].unique())

            version_filtered_df = df_prefs[df_prefs['VersionName'] == version]
            people = version_filtered_df.set_index('Name').to_dict('index')
            rooms = df_rooms[df_rooms['Accommodation'] == location].to_dict('records')
            
            # PRE-CALCULATE HISTORY MAPS
            frustration = {name: 0 for name in people.keys()}
            past_roommates = {name: set() for name in people.keys()}
            
            for _, row in df_hist.iterrows():
                p_name = row['PersonName']
                if p_name in frustration:
                    # Quality Frustration
                    if row['RoomQuality'] < 5:
                        frustration[p_name] += (10 - row['RoomQuality']) * 2
                    
                    # Find who else was in that room at that time
                    others_in_past_room = df_hist[
                        (df_hist['Accommodation'] == row['Accommodation']) & 
                        (df_hist['RoomName'] == row['RoomName']) & 
                        (df_hist['PersonName'] != p_name)
                    ]['PersonName'].tolist()
                    past_roommates[p_name].update(others_in_past_room)

            if st.button("🚀 Run Social Tetris"):
                names = list(people.keys())
                best_arr, best_score = None, -float('inf')
                
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
                            
                            # 1. Strict No
                            s_no = str(p['StrictNo']).split(',') if pd.notna(p['StrictNo']) else []
                            if any(n.strip() in others for n in s_no): score -= 10**6
                            
                            # 2. Tiers
                            t1 = [n.strip() for n in str(p['Tier1']).split(',')] if pd.notna(p['Tier1']) else []
                            t2 = [n.strip() for n in str(p['Tier2']).split(',')] if pd.notna(p['Tier2']) else []
                            
                            if any(n in others for n in t1): score += 100
                            for n in others:
                                if n in t2: score += 30
                            
                            # 3. New People Preference (The Variety Penalty)
                            if p['NewPeople'] == True:
                                for roommate in others:
                                    if roommate in past_roommates[p_name]:
                                        # Penalty only applies if they AREN'T a requested friend
                                        if roommate not in t1 and roommate not in t2:
                                            score -= 50 
                            
                            score += (r['Quality'] * 10) + (frustration[p_name] * 1.5)
                    
                    if score > best_score:
                        best_score, best_arr = score, temp_arr

                st.success(f"Best fit found (Score: {best_score})")
                for rm, folks in best_arr.items():
                    with st.expander(f"🏠 {rm}", expanded=True):
                        st.write(", ".join(folks))
                
                # Manual Entry Helper
                st.divider()
                st.write("### 📝 Copy to 'History' tab:")
                h_rows = []
                for rm, folks in best_arr.items():
                    q = next(r['Quality'] for r in rooms if r['RoomName'] == rm)
                    for p in folks: h_rows.append([location, p, rm, q, version])
                st.table(pd.DataFrame(h_rows, columns=["Accommodation", "PersonName", "RoomName", "Quality", "Version"]))

        with tab_history:
            st.subheader("Fairness Ledger")
            st.bar_chart(pd.Series(frustration))
            st.write("**Known Past Roommates (to avoid if 'NewPeople' is True):**")
            st.json({k: list(v) for k, v in past_roommates.items() if v})

    except Exception as e:
        st.error(f"Waiting for valid data... (Error: {e})")
