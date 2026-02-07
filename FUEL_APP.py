import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from scipy.signal import savgol_filter
from datetime import datetime
from fpdf import FPDF
import io

# --- 1. MUST BE THE VERY FIRST STREAMLIT COMMAND ---
st.set_page_config(page_title="Fuel Analysis Tool", layout="wide")

# --- 2. PASSWORD LOGIC ---
def password_entered():
    if st.session_state["password"] == st.secrets["password"]:
        st.session_state["password_correct"] = True
        del st.session_state["password"] 
    else:
        st.session_state["password_correct"] = False

def check_password():
    if "password_correct" not in st.session_state:
        st.text_input("Enter Hangar Access Key", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter Hangar Access Key", type="password", on_change=password_entered, key="password")
        st.error("😕 Access Denied")
        return False
    return True

if not check_password():
    st.stop() 

# --- 3. THE REST OF YOUR DATA & ENGINE ---
CORRECTION_MAP = {
    "Rated RPM (1.000)": 1.0,
    "-20 RPM (.991)": 0.991,
    "-40 RPM (.982)": 0.982,
    "-60 RPM (.973)": 0.973,
    "-80 RPM (.964)": 0.964,
    "-100 RPM (.955)": 0.955,
    "-120 RPM (.946)": 0.946
}

# ... (rest of your apply_style, create_plots, and UI code)
