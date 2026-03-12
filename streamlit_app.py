import streamlit as st
import pandas as pd
import random

# --- 1. SECURE DATA FETCHING ---
def get_data(sheet_name):
    # We pull the ID from Streamlit's hidden Secrets
    sheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    return pd.read_csv(url)

# --- 2. PASSWORD PROTECTION ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    
    if st.session_state["password_correct"]:
        return True

    # Simple sidebar login
    pwd = st.sidebar.text_input("Enter Trip Password", type="password")
    if pwd == st.secrets["password"]:
        st.session_state["password_correct"] = True
        st.rerun()
    else:
        if pwd: st.sidebar.error("Incorrect password")
        return False

# --- 3. THE APP ---
if check_password():
    try:
        # Fetching data using our secure function
        df_prefs = get_data("Preferences")
        df_rooms = get_data("Rooms")
        df_hist = get_data("History")
        
        st.success("✅ Connected to your private vault.")
        
        # Displaying the Social Map as a test
        st.subheader("Social Map Preview")
        st.dataframe(df_prefs.head())
        
        # ... (rest of your solver logic goes here)
        
    except Exception as e:
        st.error(f"Error connecting to Google Sheets. Check your Secrets and tab names. Error: {e}")
