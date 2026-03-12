import streamlit as st
import pandas as pd
import random
import copy

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

# --- Helper: Safe List Parser ---
def parse_list(val):
    if pd.isna(val) or str(val).strip() == '': return []
    return [n.strip() for n in str(val).split(',') if n.strip()]

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
            
            # --- HISTORICAL KARMA ENGINE ---
            karma = {name: 0 for name in people.keys()}
            past_roommates = {name: set() for name in people.keys()}
            
            if not df_hist.empty:
                for p_name in people.keys():
                    if 'PersonName' not in df_hist.columns: continue
                    p_hist = df_hist[df_hist['PersonName'] == p_name]
                    for _, row in p_hist.iterrows():
                        q = row.get('Quality', row.get('RoomQuality', 3)) 
                        if pd.notna(q):
                            try:
                                q = int(q)
                                if q == 1: karma[p_name] += 30
                                elif q == 2: karma[p_name] += 10
                            except: pass
                        
                        if 'Accommodation' in df_hist.columns and 'RoomName' in df_hist.columns:
                            others_hist = df_hist[
                                (df_hist['Accommodation'] == row['Accommodation']) & 
                                (df_hist['RoomName'] == row['RoomName']) & 
                                (df_hist['PersonName'] != p_name)
                            ]['PersonName'].tolist()
                            past_roommates[p_name].update([str(n).strip() for n in others_hist])
                        
                        hist_version = row.get('Version', row.get('PrefListUsed', ''))
                        if pd.notna(hist_version):
                            past_prefs = df_prefs_raw[(df_prefs_raw['VersionName'] == hist_version) & (df_prefs_raw['Name'] == p_name)]
                            if not past_prefs.empty:
                                p_past = past_prefs.iloc[0]
                                t1_past = parse_list(p_past['Tier1'])
                                t2_past = parse_list(p_past['Tier2'])
                                if 'others_hist' in locals():
                                    got_friend = any(n in others_hist for n in t1_past) or any(n in others_hist for n in t2_past)
                                    asked_for_friend = len(t1_past) > 0 or len(t2_past) > 0
                                    if asked_for_friend and not got_friend:
                                        karma[p_name] += 30

            if st.button("🚀 Run Social Tetris"):
                names = list(people.keys())
                total_cap = sum(r['Capacity'] for r in rooms)
                if total_cap < len(names):
                    st.error(f"Not enough beds! Need {len(names)}, only have {total_cap}.")
                    st.stop()

                # --- THE SCORING FUNCTION ---
                def calculate_score(arrangement):
                    score = 0
                    for r in rooms:
                        folks = arrangement[r['RoomName']]
                        if len(folks) == 0:
                            score -= 1000000 # No completely empty rooms allowed
                        
                        # Exponential Crowding Penalty (discourages packing people in unless friends)
                        score -= (len(folks) ** 2 * 10)
                        
                        for p_name in folks:
                            p = people[p_name]
                            others = [n for n in folks if n != p_name]
                            
                            s_no = parse_list(p.get('StrictNo'))
                            if any(n in others for n in s_no): score -= 1000000
                            
                            t1 = parse_list(p.get('Tier1'))
                            t2 = parse_list(p.get('Tier2'))
                            
                            t1_met = [n for n in others if n in t1]
                            t2_met = [n for n in others if n in t2]
                            
                            got_t1 = len(t1_met) > 0
                            got_t2 = len(t2_met) > 0
                            is_isolated = not got_t1 and not got_t2
                            
                            if got_t1:
                                score += 500
                                score += ((len(t1_met) - 1) + len(t2_met)) * 50
                            elif got_t2:
                                score += 200
                                score += (len(t2_met) - 1) * 50
                            
                            if is_isolated:
                                if len(t1) > 0: score -= 400
                                elif len(t2) > 0: score -= 200
                                
                            base_q = r['Quality'] * 20
                            if is_isolated and (len(t1) > 0 or len(t2) > 0): score += (base_q * 3) 
                            else: score += base_q
                                
                            score += karma[p_name]
                            
                            g_pref = str(p.get('GenderPref', 'none')).strip().lower()
                            my_gender = str(p.get('Gender', '')).strip().lower()
                            if g_pref in ['strict', 'prefer']:
                                mismatches = [n for n in others if str(people[n].get('Gender', '')).strip().lower() != my_gender and n not in t1 and n not in t2]
                                if mismatches:
                                    # STRICT IS NOW A DEALBREAKER
                                    score -= (1000000 if g_pref == 'strict' else 150)

                            is_new_people = str(p.get('NewPeople', '')).strip().lower() == 'true' or p.get('NewPeople') == True
                            if is_new_people and len(others) > 0:
                                past_in_room = [n for n in others if n in past_roommates[p_name] and n not in t1 and n not in t2]
                                if len(past_in_room) == len(others): 
                                    score -= 40
                    return score

                # --- SMART OPTIMIZER (HILL CLIMBING) ---
                progress_bar = st.progress(0)
                best_global_score = -float('inf')
                best_global_arr = None

                # We will try 15 completely different random starting points
                for restart in range(15):
                    # Create valid random starting layout
                    current_arr = {r['RoomName']: [] for r in rooms}
                    avail = {r['RoomName']: r['Capacity'] for r in rooms}
                    shuffled = list(names)
                    random.shuffle(shuffled)
                    for p in shuffled:
                        valid_rooms = [rm for rm, cap in avail.items() if len(current_arr[rm]) < cap]
                        current_arr[random.choice(valid_rooms)].append(p)
                    
                    current_score = calculate_score(current_arr)
                    
                    # Try 1,000 smart swaps per starting point
                    for step in range(1000):
                        new_arr = copy.deepcopy(current_arr)
                        r1, r2 = random.sample(list(new_arr.keys()), 2)
                        
                        move_type = random.choice([1, 2, 3]) # 1: Swap, 2: Move to r2, 3: Move to r1
                        valid_move = False
                        
                        if move_type == 1 and new_arr[r1] and new_arr[r2]:
                            p1 = random.choice(new_arr[r1])
                            p2 = random.choice(new_arr[r2])
                            new_arr[r1].remove(p1)
                            new_arr[r1].append(p2)
                            new_arr[r2].remove(p2)
                            new_arr[r2].append(p1)
                            valid_move = True
                        elif move_type == 2 and new_arr[r1]:
                            cap2 = next(r['Capacity'] for r in rooms if r['RoomName'] == r2)
                            if len(new_arr[r2]) < cap2:
                                p1 = random.choice(new_arr[r1])
                                new_arr[r1].remove(p1)
                                new_arr[r2].append(p1)
                                valid_move = True
                        elif move_type == 3 and new_arr[r2]:
                            cap1 = next(r['Capacity'] for r in rooms if r['RoomName'] == r1)
                            if len(new_arr[r1]) < cap1:
                                p2 = random.choice(new_arr[r2])
                                new_arr[r2].remove(p2)
                                new_arr[r1].append(p2)
                                valid_move = True
                                
                        if valid_move:
                            new_score = calculate_score(new_arr)
                            # Keep the swap if it's better or equal
                            if new_score >= current_score:
                                current_arr = new_arr
                                current_score = new_score

                    if current_score > best_global_score:
                        best_global_score = current_score
                        best_global_arr = current_arr
                        
                    progress_bar.progress((restart + 1) / 15)
                
                progress_bar.empty()

                # --- DISPLAY RESULTS WITH VISUALS ---
                st.success(f"Best fit found! (Algorithm Score: {best_global_score})")
                
                for rm, folks in best_global_arr.items():
                    q = next(r['Quality'] for r in rooms if r['RoomName'] == rm)
                    cap = next(r['Capacity'] for r in rooms if r['RoomName'] == rm)
                    empty_beds = cap - len(folks)
                    
                    bed_str = f"🛏️ {empty_beds} Empty Bed{'s' if empty_beds > 1 else ''}" if empty_beds > 0 else "Full"
                    
                    summary_parts = []
                    for p_name in folks:
                        p = people[p_name]
                        others = [n for n in folks if n != p_name]
                        t1 = parse_list(p.get('Tier1'))
                        t2 = parse_list(p.get('Tier2'))
                        
                        if not t1 and not t2: emoji = "😌" 
                        elif any(n in others for n in t1): emoji = "🤩" 
                        elif any(n in others for n in t2): emoji = "🙂" 
                        else: emoji = "🫠" 
                        
                        summary_parts.append(f"{p_name} {emoji}")

                    with st.expander(f"🏠 {rm} (Quality: {q}/5) [{bed_str}] ➔ {', '.join(summary_parts)}", expanded=True):
                        st.markdown("### Room Breakdown")
                        for p_name in folks:
                            p = people[p_name]
                            others = [n for n in folks if n != p_name]
                            t1 = parse_list(p.get('Tier1'))
                            t2 = parse_list(p.get('Tier2'))
                            g_pref = str(p.get('GenderPref', 'none')).strip().lower()
                            my_gender = str(p.get('Gender', '')).strip().lower()
                            is_new_people = str(p.get('NewPeople', '')).strip().lower() == 'true' or p.get('NewPeople') == True

                            st.markdown(f"**{p_name}**")
                            
                            if not t1 and not t2: st.markdown("- *😌 No specific friends requested*")
                            if t1:
                                t1_status = ", ".join([f"✅ {n}" if n in others else f"❌ {n}" for n in t1])
                                st.markdown(f"- **Tier 1:** {t1_status}")
                            if t2:
                                t2_status = ", ".join([f"✅ {n}" if n in others else f"❌ {n}" for n in t2])
                                st.markdown(f"- **Tier 2:** {t2_status}")
                            
                            if g_pref in ['strict', 'prefer']:
                                mismatches = [n for n in others if str(people[n].get('Gender', '')).strip().lower() != my_gender and n not in t1 and n not in t2]
                                if mismatches: st.markdown(f"- **Gender ({g_pref.title()}):** ❌ Mixed with {', '.join(mismatches)}")
                                else: st.markdown(f"- **Gender ({g_pref.title()}):** ✅ Match")
                            
                            if is_new_people and len(others) > 0:
                                past_in_room = [n for n in others if n in past_roommates[p_name] and n not in t1 and n not in t2]
                                if len(past_in_room) == len(others):
                                    st.markdown(f"- **Variety:** ❌ 0 new faces (With {', '.join(past_in_room)})")
                                else:
                                    st.markdown(f"- **Variety:** ✅ Satisfied")
                        st.divider()

                # --- EASY COPY EXPORTER ---
                st.write("### 📝 Save to History")
                st.info("Click the 'Copy' icon top right, then paste into the first empty row of your Google Sheets 'History' tab.")
                
                h_rows = []
                for rm, folks in best_global_arr.items():
                    q = next(r['Quality'] for r in rooms if r['RoomName'] == rm)
                    for p in folks: h_rows.append({"Accommodation": location, "PersonName": p, "RoomName": rm, "Quality": q, "Version": version})
                
                df_export = pd.DataFrame(h_rows)
                tsv_text = df_export.to_csv(sep='\t', index=False, header=False)
                st.code(tsv_text, language="text")

        with tab_history:
            st.subheader("Fairness Ledger")
            st.write("Current Accumulated Karma (Higher = Gets priority for better rooms)")
            st.bar_chart(pd.Series(karma))
            st.write("**Past Roommates (Rotating targets):**")
            st.json({k: list(v) for k, v in past_roommates.items() if v})

    except Exception as e:
        st.error(f"Something is wrong in your Google Sheet format. Error: {e}")
