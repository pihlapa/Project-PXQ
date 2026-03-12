import streamlit as st
import pandas as pd
import random
import requests

# --- 1. SECURE DATA FETCHING ---
def get_data(sheet_name):
    sheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    return pd.read_csv(url)

# --- 2. LOGIN LOGIC ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True
    
    st.markdown("### 🔐 Secure Trip Access")
    pwd = st.text_input("Enter Trip Password", type="password")
    if st.button("Log In"):
        if pwd == st.secrets["password"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Incorrect password")
    return False

# --- 3. MAIN APP ---
if check_password():
    try:
        df_prefs = get_data("Preferences")
        df_rooms = get_data("Rooms")
        df_hist = get_data("History")
        
        tab_solve, tab_data, tab_history = st.tabs(["🎲 Solver", "📊 Current Data", "📜 History"])

        with tab_data:
            st.subheader("Live Data from Google Sheets")
            st.write("**Social Map Versions:**", df_prefs['VersionName'].unique())
            st.dataframe(df_prefs)
            st.subheader("Accommodation List")
            st.dataframe(df_rooms)

        with tab_solve:
            st.subheader("Generate New Arrangement")
            
            col1, col2 = st.columns(2)
            with col1:
                version = st.selectbox("Select Social Version", df_prefs['VersionName'].unique())
            with col2:
                location = st.selectbox("Select Location", df_rooms['Accommodation'].unique())

            people = df_prefs[df_prefs['VersionName'] == version].set_index('Name').to_dict('index')
            rooms = df_rooms[df_rooms['Accommodation'] == location].to_dict('records')
            
            # Calculate Frustration from History
            frustration = {name: 0 for name in people.keys()}
            for _, row in df_hist.iterrows():
                if row['PersonName'] in frustration:
                    if row['RoomQuality'] < 5:
                        frustration[row['PersonName']] += (10 - row['RoomQuality']) * 2

            # Initialization for the state
            if "best_arr" not in st.session_state:
                st.session_state.best_arr = None

            if st.button("🚀 Calculate Best Fit"):
                names = list(people.keys())
                best_arr, best_score = None, -float('inf')
                
                progress = st.progress(0)
                for i in range(2000):
                    random.shuffle(names)
                    temp_arr, idx, score = {}, 0, 0
                    for r in rooms:
                        occupants = names[idx : idx + r['Capacity']]
                        temp_arr[r['RoomName']] = occupants
                        idx += r['Capacity']
                        for p_name in occupants:
                            p = people[p_name]
                            others = [n for n in occupants if n != p_name]
                            s_no = str(p['StrictNo']).split(',') if pd.notna(p['StrictNo']) else []
                            if any(n.strip() in others for n in s_no): score -= 10**6
                            t1 = str(p['Tier1']).split(',') if pd.notna(p['Tier1']) else []
                            if any(n.strip() in others for n in t1): score += 100
                            t2 = str(p['Tier2']).split(',') if pd.notna(p['Tier2']) else []
                            for n in others:
                                if n.strip() in t2: score += 30
                            score += (r['Quality'] * 10) + (frustration[p_name] * 1.5)
                    
                    if score > best_score:
                        best_score, best_arr = score, temp_arr
                    if i % 200 == 0: progress.progress(i / 2000)
                
                progress.empty()
                st.session_state.best_arr = best_arr
                st.session_state.last_score = best_score

            # Display Results and Save Button
            if st.session_state.best_arr:
                st.success(f"Optimized Layout Found! Score: {st.session_state.last_score}")
                for rm, folks in st.session_state.best_arr.items():
                    with st.expander(f"🏠 {rm}", expanded=True):
                        st.write(", ".join(folks))
                
                # PREPARE HISTORY DATA
                history_payload = []
                for rm, folks in st.session_state.best_arr.items():
                    # Find quality for this room
                    q = next(r['Quality'] for r in rooms if r['RoomName'] == rm)
                    for p_name in folks:
                        history_payload.append({
                            "Accommodation": location,
                            "PersonName": p_name,
                            "RoomName": rm,
                            "RoomQuality": q,
                            "PrefListUsed": version
                        })

                if st.button("✅ Lock & Save to History"):
                    try:
                        # Send to Google Apps Script
                        resp = requests.post(st.secrets["script_url"], json=history_payload)
                        if resp.status_code == 200:
                            st.success("🎉 Successfully saved to Google Sheets!")
                            st.balloons()
                        else:
                            st.error(f"Failed to save. Status: {resp.status_code}")
                    except Exception as e:
                        st.error(f"Error connecting to Script: {e}")

        with tab_history:
            st.subheader("Trip History & Fairness")
            st.bar_chart(pd.Series(frustration))
            st.dataframe(df_hist)

    except Exception as e:
        st.error(f"Error: {e}")
