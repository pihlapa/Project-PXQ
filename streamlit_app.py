import streamlit as st
import pandas as pd
import random

# --- 1. SECURE DATA FETCHING ---
def get_data(sheet_name):
    sheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    return pd.read_csv(url)

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
        df_prefs = get_data("Preferences")
        df_rooms = get_data("Rooms")
        df_hist = get_data("History")
        
        tab_solve, tab_data, tab_history = st.tabs(["🎲 Solver", "📊 Live Data", "📜 Fairness Log"])

        with tab_solve:
            st.subheader("Generate Arrangement")
            
            # Select Version and Location
            v_options = df_prefs['VersionName'].unique()
            l_options = df_rooms['Accommodation'].unique()
            
            col1, col2 = st.columns(2)
            version = col1.selectbox("Social Map", v_options)
            location = col2.selectbox("Location", l_options)

            people = df_prefs[df_prefs['VersionName'] == version].set_index('Name').to_dict('index')
            rooms = df_rooms[df_rooms['Accommodation'] == location].to_dict('records')
            
            # Calculate Frustration from History
            frustration = {name: 0 for name in people.keys()}
            for _, row in df_hist.iterrows():
                if row['PersonName'] in frustration:
                    if row['RoomQuality'] < 5:
                        frustration[row['PersonName']] += (10 - row['RoomQuality']) * 2

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
                            
                            # Scoring
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

                st.success(f"Best fit found (Score: {best_score})")
                
                # DISPLAY ROOMS
                for rm, folks in best_arr.items():
                    with st.expander(f"🏠 {rm}", expanded=True):
                        st.write(", ".join(folks))
                
                # MANUAL ENTRY ASSISTANT
                st.divider()
                st.write("### 📝 Copy this to Google Sheets 'History' tab:")
                history_rows = []
                for rm, folks in best_arr.items():
                    q = next(r['Quality'] for r in rooms if r['RoomName'] == rm)
                    for p in folks:
                        history_rows.append([location, p, rm, q, version])
                
                # Show as a table you can easily read from your phone
                st.table(pd.DataFrame(history_rows, columns=["Accommodation", "PersonName", "RoomName", "Quality", "Version"]))

        with tab_history:
            st.subheader("Fairness Ledger")
            st.write("Higher bars = these people deserve the best rooms next time!")
            st.bar_chart(pd.Series(frustration))
            st.dataframe(df_hist)

    except Exception as e:
        st.error(f"Waiting for valid data... (Error: {e})")
