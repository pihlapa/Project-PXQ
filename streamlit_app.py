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
                                illegal_genders = [n for n in others if str(people[n].get('Gender', '')).strip().lower() != my_gender and n not in t1 and n not in t2]
                                if illegal_genders:
                                    score -= (150 if g_pref == 'strict' else 60)

                            # New People Variety Logic
                            is_new_people = str(p.get('NewPeople', '')).strip().lower() == 'true' or p.get('NewPeople') == True
                            if is_new_people:
                                for roommate in others:
                                    if roommate in past_roommates[p_name] and roommate not in t1 and roommate not in t2:
                                        score -= 50 
                            
                            # Fairness/Frustration
                            score += (r['Quality'] * 10) + (frustration[p_name] * 1.5)
                    
                    if score > best_score:
                        best_score, best_arr = score, temp_arr

                # --- DISPLAY RESULTS WITH VISUALS ---
                st.success(f"Best fit found! (Algorithm Score: {best_score})")
                
                for rm, folks in best_arr.items():
                    q = next(r['Quality'] for r in rooms if r['RoomName'] == rm)
                    
                    # 1. High-level summary string
                    summary_parts = []
                    for p_name in folks:
                        p = people[p_name]
                        others = [n for n in folks if n != p_name]
                        t1 = [n.strip() for n in str(p['Tier1']).split(',')] if pd.notna(p['Tier1']) and str(p['Tier1']).strip() else []
                        t2 = [n.strip() for n in str(p['Tier2']).split(',')] if pd.notna(p['Tier2']) and str(p['Tier2']).strip() else []
                        
                        if not t1 and not t2: emoji = "😌"
                        elif any(n in others for n in t1): emoji = "🤩"
                        elif any(n in others for n in t2): emoji = "🙂"
                        else: emoji = "🫠"
                        
                        summary_parts.append(f"{p_name} {emoji}")

                    # 2. Expander with Room Quality and Detailed Breakdown
                    with st.expander(f"🏠 {rm} (Quality: {q}/10)  ➔  {', '.join(summary_parts)}", expanded=True):
                        st.markdown("### Room Breakdown")
                        for p_name in folks:
                            p = people[p_name]
                            others = [n for n in folks if n != p_name]
                            
                            t1 = [n.strip() for n in str(p['Tier1']).split(',')] if pd.notna(p['Tier1']) and str(p['Tier1']).strip() else []
                            t2 = [n.strip() for n in str(p['Tier2']).split(',')] if pd.notna(p['Tier2']) and str(p['Tier2']).strip() else []
                            g_pref = str(p.get('GenderPref', 'none')).strip().lower()
                            my_gender = str(p.get('Gender', '')).strip().lower()
                            is_new_people = str(p.get('NewPeople', '')).strip().lower() == 'true' or p.get('NewPeople') == True

                            st.markdown(f"**{p_name}**")
                            
                            # Tiers display
                            if not t1 and not t2:
                                st.markdown("- *No specific friends requested*")
                            if t1:
                                t1_status = ", ".join([f"✅ {n}" if n in others else f"❌ {n}" for n in t1])
                                st.markdown(f"- **Tier 1:** {t1_status}")
                            if t2:
                                t2_status = ", ".join([f"✅ {n}" if n in others else f"❌ {n}" for n in t2])
                                st.markdown(f"- **Tier 2:** {t2_status}")
                            
                            # Gender display
                            if g_pref in ['strict', 'prefer']:
                                mismatches = [n for n in others if str(people[n].get('Gender', '')).strip().lower() != my_gender and n not in t1 and n not in t2]
                                if mismatches:
                                    st.markdown(f"- **Gender ({g_pref.title()}):** ❌ Mixed with {', '.join(mismatches)}")
                                else:
                                    st.markdown(f"- **Gender ({g_pref.title()}):** ✅ Match (or with requested friends)")
                            else:
                                st.markdown("- **Gender:** 😌 No preference")

                            # New People display
                            if is_new_people:
                                past_in_room = [n for n in others if n in past_roommates[p_name] and n not in t1 and n not in t2]
                                if past_in_room:
                                    st.markdown(f"- **Variety:** ❌ With past roommates ({', '.join(past_in_room)})")
                                else:
                                    st.markdown(f"- **Variety:** ✅ All new faces (or requested friends)")
                            
                        st.divider()

                # --- EASY COPY EXPORTER ---
                st.write("### 📝 Save to History")
                st.info("Click the 'Copy' icon in the top right of the box below, then paste into the first empty row of your Google Sheets 'History' tab.")
                
                h_rows = []
                for rm, folks in best_arr.items():
                    q = next(r['Quality'] for r in rooms if r['RoomName'] == rm)
                    for p in folks: h_rows.append({"Accommodation": location, "PersonName": p, "RoomName": rm, "Quality": q, "Version": version})
                
                df_export = pd.DataFrame(h_rows)
                tsv_text = df_export.to_csv(sep='\t', index=False, header=False)
                st.code(tsv_text, language="text")

        with tab_history:
            st.subheader("Fairness Ledger")
            st.bar_chart(pd.Series(frustration))
            st.write("**Past Roommates (Rotating targets):**")
            st.json({k: list(v) for k, v in past_roommates.items() if v})

    except Exception as e:
        st.error(f"Something is wrong in your Google Sheet format. Error: {e}")
