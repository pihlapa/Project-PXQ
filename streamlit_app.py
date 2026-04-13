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

# --- Helper: Deep String Cleaner ---
def clean_str(val):
    if pd.isna(val): return ""
    s = str(val).strip()
    if s.lower() == 'nan': return ""
    if s.endswith('.0'): s = s[:-2]
    return s

# --- Epic Group Chat Emojis ---
CHAT_EMOJIS = [
    "🤑", "🤠", "😈", "👹", "🤡", "💀", "👽", "🤝", "🤌", "🫰", "💪", "🦷", "👀", "🫀", "🫁", "🧠", 
    "💂", "🧑‍🍳", "🧑‍⚖️", "🦸", "🧑🏻‍🎄", "🧚", "🧜", "🧞", "💅", "💃", "🕺", "👯", "🦺", "👙", "👖", "👠", 
    "🧦", "🧢", "🎩", "👒", "🎓", "⛑", "🪖", "👑", "🕶", "🥽", "🐭", "🐰", "🐻", "🐨", "🐯", "🦁", 
    "🐮", "🐷", "🐸", "🐒", "🐥", "🦆", "🦄", "🐝", "🐛", "🐌", "🕷", "🐢", "🐍", "🦕", "🦀", "🐙", 
    "🐳", "🐡", "🐊", "🐫", "🐏", "🐓", "🦩", "🐀", "🌵", "🎄", "🌴", "🍀", "🍄", "🥀", "🌺", "🌻", 
    "🌚", "🌎", "💫", "💥", "☄️", "⚡️", "✨", "🔥", "🌪", "🌈", "☀️", "⛅️", "🌧", "🌊", "🍌", "🍋", 
    "🍓", "🍒", "🍑", "🍍", "🥥", "🥑", "🌶", "🥕", "🥐", "🥖", "🧀", "🥚", "🧇", "🍕", "🍟", "🌮", 
    "🌯", "🥗", "🍝", "🍣", "🍦", "🍰", "🍭", "🍬", "🍫", "🍿", "🍩", "☕️", "🥂", "🧃", "🍺", "🍷", 
    "🥃", "🍸", "🍹", "🍾", "🧊", "🧂", "⚽️", "🏈", "🏀", "🎱", "🏓", "⛳️", "🥊", "🪁", "🥌", "🪂", 
    "🤸", "🏄", "🏆", "🏅", "🚣", "🎪", "🤹🏻", "🎨", "🎬", "🎧", "🥁", "🎺", "🎯", "♟", "🧩", "🚗", 
    "🏎", "🚓", "🚑", "🚒", "🛵", "🛺", "🚠", "🚂", "🚀", "⛵️", "🛟", "⚓️", "🗽", "🎢", "🏝", "⛺️", 
    "🏗", "☎️", "📺", "🧭", "⏳", "🔋", "🪫", "💡", "💸", "💰", "💎", "⚖️", "🛠", "🪤", "🧲", "🔮", 
    "🦠", "🧻", "🪣", "🔑", "🚪", "🎁", "🎉", "🪩", "💌", "📦", "📈", "🔒", "🆘", "💯", "⛔️", "📵", 
    "🚭", "🔞", "⚠️", "🚸", "♻️", "💤", "🆒", "🎶", "📣", "💬", "💭", "🗯", "😇", "🤪", "🤓"
]

# --- 3. MAIN APP ---
if check_password():
    try:
        # 1. LOAD DATA
        df_prefs_raw = get_data("Preferences")
        df_rooms_raw = get_data("Rooms")
        df_hist = get_data("History")
        
        # 2. GLOBAL DATA SANITIZATION (Fixes merge and capacity bugs)
        if not df_rooms_raw.empty:
            df_rooms_raw['Accommodation'] = df_rooms_raw['Accommodation'].apply(clean_str)
            df_rooms_raw['RoomName'] = df_rooms_raw['RoomName'].apply(clean_str)
            
            # --- KILL ONLY TRUE GHOST ROWS (Where BOTH Accommodation & RoomName are blank) ---
            df_rooms_raw = df_rooms_raw[~((df_rooms_raw['Accommodation'] == "") & (df_rooms_raw['RoomName'] == ""))]
            
            df_rooms_raw['Capacity'] = pd.to_numeric(df_rooms_raw['Capacity'], errors='coerce').fillna(0).astype(int)
            
        if not df_hist.empty:
            df_hist['RoomName'] = df_hist['RoomName'].apply(clean_str)
            df_hist['Accommodation'] = df_hist['Accommodation'].apply(clean_str)
            # Safe merge
            df_hist_master = pd.merge(df_hist, df_rooms_raw[['Accommodation', 'RoomName', 'Capacity']], on=['Accommodation', 'RoomName'], how='left')
            df_hist_master['Capacity'] = df_hist_master['Capacity'].fillna(0).astype(int)
        else:
            df_hist_master = None

        tab_solve, tab_data, tab_history = st.tabs(["🎲 Solver", "📊 Live Data", "📜 Fairness Log"])

        # ==========================================
        #               DATA TAB
        # ==========================================
        with tab_data:
            st.subheader("Historical Arrangement Overview")
            
            if df_hist_master is None or df_hist_master.empty:
                st.info("Run the solver and save some history to see visuals.")
            else:
                st.markdown("**Color Key:** 🟩 Happy (Got T1 / No requests) | 🟨 Compromised (T2) | 🟧 Isolated (No wishes met)")
                st.divider()
                
                unique_accommodations = df_hist_master['Accommodation'].unique()
                for acc_name in unique_accommodations:
                    st.markdown(f"### {acc_name}")
                    
                    df_acc_hist = df_hist_master[df_hist_master['Accommodation'] == acc_name]
                    rm_version = df_acc_hist['Version'].iloc[0] 
                    unique_rooms = df_acc_hist['RoomName'].unique()
                    
                    max_cap = 0
                    for rm in unique_rooms:
                        rm_cap = df_acc_hist[df_acc_hist['RoomName'] == rm]['Capacity'].max()
                        if pd.isna(rm_cap) or rm_cap == 0:
                            rm_cap = len(df_acc_hist[df_acc_hist['RoomName'] == rm])
                        max_cap = max(max_cap, int(rm_cap))
                    
                    grid_data = {}
                    style_data = {}
                    
                    for rm in unique_rooms:
                        df_rm = df_acc_hist[df_acc_hist['RoomName'] == rm]
                        occupants = df_rm['PersonName'].tolist()
                        rm_cap = int(df_rm['Capacity'].max()) if not pd.isna(df_rm['Capacity'].max()) and df_rm['Capacity'].max() > 0 else len(occupants)
                        
                        col_text = []
                        col_style = []
                        
                        for person in occupants:
                            person_prefs = df_prefs_raw[(df_prefs_raw['VersionName'] == rm_version) & (df_prefs_raw['Name'] == person)]
                            color = "background-color: #A7D3A6; color: black;" # Default Green
                            
                            if not person_prefs.empty:
                                p_data = person_prefs.iloc[0]
                                t1 = parse_list(p_data.get('Tier1'))
                                t2 = parse_list(p_data.get('Tier2'))
                                others = [n for n in occupants if n != person]
                                
                                got_t1 = any(n in others for n in t1)
                                got_t2 = any(n in others for n in t2)
                                
                                if len(t1) > 0 or len(t2) > 0:
                                    if got_t1: color = "background-color: #A7D3A6; color: black;" 
                                    elif got_t2: color = "background-color: #FDE49C; color: black;" 
                                    else: color = "background-color: #FCB97D; color: black;" 
                                    
                            col_text.append(person)
                            col_style.append(color)
                            
                        empty_count = rm_cap - len(occupants)
                        for _ in range(empty_count):
                            col_text.append("🛏️ Empty Bed")
                            col_style.append("background-color: #f1f3f5; color: #adb5bd; font-style: italic;")
                            
                        while len(col_text) < max_cap:
                            col_text.append("")
                            col_style.append("")
                            
                        grid_data[rm] = col_text
                        style_data[rm] = col_style
                    
                    df_grid = pd.DataFrame(grid_data)
                    df_style = pd.DataFrame(style_data)
                    styled_grid = df_grid.style.apply(lambda _: df_style, axis=None)
                    
                    st.dataframe(styled_grid, use_container_width=True, hide_index=True)
                    st.divider()

            st.subheader("Raw Live Data from Google Sheets")
            col1, col2 = st.columns(2)
            col1.write("### Preferences")
            col1.dataframe(df_prefs_raw)
            col2.write("### Rooms")
            col2.dataframe(df_rooms_raw)
            st.divider()

            st.subheader("Group Chat Messages")
            if df_hist_master is None or df_hist_master.empty:
                st.info("Save an arrangement to see its group message.")
            else:
                unique_arrangements = df_hist_master[['Accommodation', 'Version']].drop_duplicates()
                for index, arr_row in unique_arrangements.iterrows():
                    arr_acc = arr_row['Accommodation']
                    arr_ver = arr_row['Version']
                    
                    msg_text = f"Room Solver results for {arr_acc}\n\n"
                    
                    df_arr_full = df_hist_master[(df_hist_master['Accommodation'] == arr_acc) & (df_hist_master['Version'] == arr_ver)]
                    unique_arr_rooms = df_arr_full['RoomName'].unique()
                    
                    for rm_name in unique_arr_rooms:
                        df_rm_data = df_arr_full[df_arr_full['RoomName'] == rm_name]
                        arr_cap = int(df_rm_data['Capacity'].iloc[0]) if not df_rm_data['Capacity'].isna().all() and df_rm_data['Capacity'].iloc[0] > 0 else "?"
                        occupants = df_rm_data['PersonName'].tolist()
                        
                        emoji = random.choice(CHAT_EMOJIS)
                        msg_text += f"{emoji} {rm_name} {len(occupants)}/{arr_cap}\n"
                        msg_text += f"{', '.join(occupants)}\n\n"
                    
                    st.code(msg_text.strip(), language="text")

        # ==========================================
        #               SOLVER TAB
        # ==========================================
        with tab_solve:
            st.subheader("Generate Arrangement")
            
            v_options = df_prefs_raw['VersionName'].unique()
            l_options = df_rooms_raw['Accommodation'].unique()
            
            col1, col2 = st.columns(2)
            version = col1.selectbox("Social Map Version", v_options)
            location = col2.selectbox("Location", l_options)

            df_filtered = df_prefs_raw[df_prefs_raw['VersionName'] == version].copy()
            df_filtered['Name'] = df_filtered['Name'].astype(str).str.strip()
            
            # --- KILL GHOST ROWS IN PREFERENCES ---
            df_filtered = df_filtered[df_filtered['Name'] != ""]
            
            duplicate_names = df_filtered[df_filtered.duplicated(['Name'])]['Name'].tolist()
            if duplicate_names:
                st.error(f"🚨 Duplicate Name Detected: {', '.join(duplicate_names)}.")
                st.stop()
            
            people = df_filtered.set_index('Name').to_dict('index')
            rooms = df_rooms_raw[df_rooms_raw['Accommodation'] == location].to_dict('records')
            
            # --- BLANK & DUPLICATE ROOM PROTECTION ---
            room_names = [r['RoomName'] for r in rooms]
            
            if "" in room_names:
                st.error("🚨 One or more rooms in this Accommodation are missing a name! Please ensure every room has a name in Google Sheets.")
                st.stop()
                
            if len(room_names) != len(set(room_names)):
                st.error("🚨 Duplicate Room Names detected in your Google Sheet for this Accommodation! Please make sure every room has a unique name (e.g. Room 1, Room 2).")
                st.stop()
            
            karma = {name: 0 for name in people.keys()}
            past_roommates = {name: set() for name in people.keys()}
            
            if not df_hist.empty:
                df_hist['RoomName'] = df_hist['RoomName'].apply(clean_str)
                df_hist['Accommodation'] = df_hist['Accommodation'].apply(clean_str)
                
                for p_name in people.keys():
                    if 'PersonName' not in df_hist.columns: continue
                    p_hist = df_hist[df_hist['PersonName'] == p_name]
                    for _, row in p_hist.iterrows():
                        q = row.get('Quality', row.get('RoomQuality', 3)) 
                        if pd.notna(q):
                            try:
                                q = int(float(q)) 
                                if q == 1: karma[p_name] += 30
                                elif q == 2: karma[p_name] += 10
                            except: pass
                        
                        if 'Accommodation' in df_hist.columns and 'RoomName' in df_hist.columns:
                            others_hist = df_hist[
                                (df_hist['Accommodation'] == clean_str(row['Accommodation'])) & 
                                (df_hist['RoomName'] == clean_str(row['RoomName'])) & 
                                (df_hist['PersonName'] != p_name)
                            ]['PersonName'].tolist()
                            past_roommates[p_name].update([clean_str(n) for n in others_hist])
                        
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

                def calculate_score(arrangement):
                    score = 0
                    for r in rooms:
                        folks = arrangement[r['RoomName']]
                        if len(folks) == 0:
                            score -= 1000000 
                        
                        score -= (len(folks) ** 2 * 10)
                        
                        for p_name in folks:
                            p = people[p_name]
                            others = [n for n in folks if n != p_name]
                            
                            s_no = parse_list(p.get('StrictNo'))
                            if any(n in others for n in s_no): score -= 1000000
                            
                            # --- NEW: SOFT NO PENALTY ---
                            soft_no = parse_list(p.get('SoftNo'))
                            soft_no_met = [n for n in others if n in soft_no]
                            score -= (len(soft_no_met) * 220)
                            
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
                                    score -= (1000000 if g_pref == 'strict' else 150)

                            is_new_people = str(p.get('NewPeople', '')).strip().lower() == 'true' or p.get('NewPeople') == True
                            if is_new_people and len(others) > 0:
                                past_in_room = [n for n in others if n in past_roommates[p_name] and n not in t1 and n not in t2]
                                if len(past_in_room) == len(others): 
                                    score -= 40
                    return score

                progress_bar = st.progress(0)
                best_global_score = -float('inf')
                best_global_arr = None

                for restart in range(15):
                    current_arr = {r['RoomName']: [] for r in rooms}
                    avail = {r['RoomName']: r['Capacity'] for r in rooms}
                    shuffled = list(names)
                    random.shuffle(shuffled)
                    for p in shuffled:
                        valid_rooms = [rm for rm, cap in avail.items() if len(current_arr[rm]) < cap]
                        current_arr[random.choice(valid_rooms)].append(p)
                    
                    current_score = calculate_score(current_arr)
                    
                    for step in range(1000):
                        new_arr = copy.deepcopy(current_arr)
                        r1, r2 = random.sample(list(new_arr.keys()), 2)
                        
                        move_type = random.choice([1, 2, 3]) 
                        valid_move = False
                        
                        if move_type == 1 and new
