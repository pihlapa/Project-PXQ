import streamlit as st
import pandas as pd
import random
from streamlit_gsheets import GSheetsConnection

# 1. Login Logic
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    
    if st.session_state["password_correct"]:
        return True

    pwd = st.sidebar.text_input("Enter Trip Password", type="password")
    if pwd == st.secrets.get("password", "travel2026"): # Fallback pwd
        st.session_state["password_correct"] = True
        st.rerun()
    else:
        if pwd: st.sidebar.error("Incorrect password")
        return False

if check_password():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Load Data
    df_prefs = conn.read(worksheet="Preferences")
    df_rooms = conn.read(worksheet="Rooms")
    df_hist = conn.read(worksheet="History")

    tab_solve, tab_manage = st.tabs(["🎲 Solver", "⚙️ Data Management"])

    with tab_solve:
        st.subheader("Generate Arrangement")
        
        # Select Version and Location
        col1, col2 = st.columns(2)
        with col1:
            version = st.selectbox("Social Map Version", df_prefs['VersionName'].unique())
        with col2:
            location = st.selectbox("Target Location", df_rooms['Accommodation'].unique())

        # Filter Data
        current_prefs = df_prefs[df_prefs['VersionName'] == version].set_index('Name').to_dict('index')
        current_rooms = df_rooms[df_rooms['Accommodation'] == location].to_dict('records')
        
        # Calculate Frustration from History
        frustration = {name: 0 for name in current_prefs.keys()}
        for _, row in df_hist.iterrows():
            if row['PersonName'] in frustration:
                # Add points if they had a bad room previously (Q < 5)
                if row['RoomQuality'] < 5:
                    frustration[row['PersonName']] += (10 - row['RoomQuality']) * 2

        if st.button("Calculate Best Arrangement"):
            # --- THE ENGINE ---
            names = list(current_prefs.keys())
            best_arr, best_score = None, -float('inf')
            
            # Run 5000 random simulations
            for _ in range(5000):
                random.shuffle(names)
                temp_arr, idx = {}, 0
                score = 0
                
                for r in current_rooms:
                    occupants = names[idx : idx + r['Capacity']]
                    temp_arr[r['RoomName']] = occupants
                    idx += r['Capacity']
                    
                    # Scoring Logic
                    for p_name in occupants:
                        p = current_prefs[p_name]
                        others = [n for n in occupants if n != p_name]
                        
                        # Hard Constraint: Strict No
                        strict_no_list = str(p['StrictNo']).split(',') if p['StrictNo'] else []
                        if any(n.strip() in others for n in strict_no_list):
                            score -= 10**6 
                        
                        # Tier 1 Bonus
                        t1_list = str(p['Tier1']).split(',') if p['Tier1'] else []
                        if any(n.strip() in others for n in t1_list): score += 100
                        
                        # Equity boost
                        score += (r['Quality'] * 10) + (frustration[p_name] * 1.5)
                
                if score > best_score:
                    best_score, best_arr = score, temp_arr

            st.write(f"### Results (Score: {best_score})")
            for rm, folks in best_arr.items():
                st.info(f"**{rm}**: {', '.join(folks)}")
            
            st.warning("Note: To save this to history, manually add these rows to your Google Sheet 'History' tab.")

    with tab_manage:
        st.write("### Data Status")
        st.write(f"Total People: {len(df_prefs[df_prefs['VersionName']==version])}")
        st.write(f"Total Rooms for {location}: {len(current_rooms)}")
        st.dataframe(df_prefs)
