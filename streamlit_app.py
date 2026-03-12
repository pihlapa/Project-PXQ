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
    if st.session_state["password_correct"]:
        return True
    
    # Custom login UI
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
        # Load all data tabs
        df_prefs = get_data("Preferences")
        df_rooms = get_data("Rooms")
        df_hist = get_data("History")
        
        tab_solve, tab_data, tab_history = st.tabs(["🎲 Solver", "📊 Current Data", "📜 History"])

        with tab_data:
            st.subheader("Current Social Map (Live from Google Sheets)")
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

            # Prepare Data for Solver
            people = df_prefs[df_prefs['VersionName'] == version].set_index('Name').to_dict('index')
            rooms = df_rooms[df_rooms['Accommodation'] == location].to_dict('records')
            
            # Calculate Frustration from History
            frustration = {name: 0 for name in people.keys()}
            for _, row in df_hist.iterrows():
                if row['PersonName'] in frustration:
                    # Penalty for poor room quality
                    if row['RoomQuality'] < 5:
                        frustration[row['PersonName']] += (10 - row['RoomQuality']) * 2
                    # Penalty for no friends (if they had wishes)
                    # Note: We'd need to check roommates in history for full logic, 
                    # but quality tracking is the biggest fairness driver.

            if st.button("🚀 Calculate Best Fit"):
                names = list(people.keys())
                best_arr, best_score = None, -float('inf')
                
                # Progress bar for the "Dice Rolling"
                progress = st.progress(0)
                for i in range(2000): # 2000 simulations
                    random.shuffle(names)
                    temp_arr, idx, score = {}, 0, 0
                    
                    for r in rooms:
                        occupants = names[idx : idx + r['Capacity']]
                        temp_arr[r['RoomName']] = occupants
                        idx += r['Capacity']
                        
                        for p_name in occupants:
                            p = people[p_name]
                            others = [n for n in occupants if n != p_name]
                            
                            # 1. Strict No - Huge Penalty
                            s_no = str(p['StrictNo']).split(',') if pd.notna(p['StrictNo']) else []
                            if any(n.strip() in others for n in s_no): score -= 10**6
                            
                            # 2. Tier 1 - Flat Bonus (At least one)
                            t1 = str(p['Tier1']).split(',') if pd.notna(p['Tier1']) else []
                            if any(n.strip() in others for n in t1): score += 100
                            
                            # 3. Tier 2 - Stackable Bonus
                            t2 = str(p['Tier2']).split(',') if pd.notna(p['Tier2']) else []
                            for n in others:
                                if n.strip() in t2: score += 30
                            
                            # 4. Gender logic
                            if p['GenderPref'] in ['strict', 'prefer']:
                                illegal = [n for n in others if people[n]['Gender'] != p['Gender'] 
                                           and n.strip() not in t1 and n.strip() not in t2]
                                if illegal:
                                    score -= (150 if p['GenderPref'] == 'strict' else 60)
                            
                            # 5. Room Quality + Fairness
                            score += (r['Quality'] * 10) + (frustration[p_name] * 1.5)
                    
                    if score > best_score:
                        best_score, best_arr = score, temp_arr
                    if i % 200 == 0: progress.progress(i / 2000)
                
                progress.empty()
                st.success(f"Optimized Layout Found! Score: {best_score}")
                
                for rm, folks in best_arr.items():
                    with st.expander(f"🏠 {rm} (Cap: {len(folks)})", expanded=True):
                        st.write(", ".join(folks))
                
                st.info("💡 Happy with this? Don't forget to manually update your 'History' tab in Google Sheets so the next round stays fair!")

        with tab_history:
            st.subheader("Trip History & Fairness")
            st.write("Current 'Frustration' levels (Higher = priority for a better room next time):")
            st.bar_chart(pd.Series(frustration))
            st.dataframe(df_hist)

    except Exception as e:
        st.error(f"Oops! Something went wrong. Check your Google Sheet column names and tab names. Error: {e}")
