import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from scipy.signal import savgol_filter
from datetime import datetime
from fpdf import FPDF
import io

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="SR22(T) Fuel Tool", layout="wide")

st.markdown("""
    <style>
        /* Hide Streamlit Branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Adjust top padding for a cleaner look */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 0rem;
        }

        .stApp { background-color: white !important; }
        section[data-testid="stSidebar"] { background-color: #f0f2f6 !important; }
        p, h1, h2, h3, label { color: #31333f !important; }
        
        /* Custom Button Styling */
        div.stButton > button:first-child {
            background-color: #e0e6ed;
            color: #1a1c23;
            border: 1px solid #ccd4dc;
            font-weight: bold;
        }
        div.stButton > button:hover {
            background-color: #d1d9e2;
            border: 1px solid #1a1c23;
            color: #1a1c23;
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. PASSWORD GATEKEEPER ---
def password_entered():
    if st.session_state["password"] == st.secrets["password"]:
        st.session_state["password_correct"] = True
        del st.session_state["password"] 
    else: st.session_state["password_correct"] = False

if "password_correct" not in st.session_state or not st.session_state["password_correct"]:
    try: st.image("logo.png", width=200)
    except: pass
    st.title("🔒 Hangar Access Required")
    st.text_input("Enter Access Key", type="password", on_change=password_entered, key="password")
    st.stop()

# --- 3. CONSTANTS ---
CORRECTION_MAP = {
    "Rated RPM (1.000)": 1.0, "-20 RPM (.991)": 0.991, "-40 RPM (.982)": 0.982,
    "-60 RPM (.973)": 0.973, "-80 RPM (.964)": 0.964, "-100 RPM (.955)": 0.955, "-120 RPM (.946)": 0.946
}

# --- 4. HELPERS ---
def apply_style(fig, title):
    fig.update_layout(
        template="plotly_white", paper_bgcolor="white", plot_bgcolor="white",
        title={'text': f"<b>{title}</b>", 'y': 0.95, 'x': 0.5, 'xanchor': 'center', 'font': {'size': 20}},
        hovermode="x", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=70, r=70, t=110, b=70),
        xaxis=dict(showspikes=True, gridcolor="#e5e5e5", linecolor="black", title_text="<b>Time (s)</b>"),
        yaxis=dict(gridcolor="#e5e5e5", linecolor="black", ticksuffix=" PSI", title_text="<b>Pressure (PSI)</b>")
    )

def add_label(fig, y, text, color, x=0.01):
    fig.add_annotation(xref="paper", x=x, y=y, text=f"<b>{text}</b>", showarrow=False, 
                       font=dict(color=color, size=11), bgcolor="white", bordercolor=color, borderwidth=2, borderpad=6)

def add_peak_marker(fig, x_data, y_data, name, color, is_min=False):
    idx = y_data.argmin() if is_min else y_data.argmax()
    fig.add_trace(go.Scatter(
        x=[x_data.iloc[idx]], y=[y_data[idx]],
        mode="markers+text", name=name,
        text=[f"<b>{y_data[idx]:.2f}</b>"], textposition="top center",
        marker=dict(color=color, size=12, line=dict(width=2, color="white"))
    ))

# --- 5. UI LAYOUT & MODE RESET ---
try: st.sidebar.image("logo.png", width=180)
except: pass

st.title("SR22(T) Fuel Pressure Diagnostic Tool")

def reset_engine_mode():
    st.session_state["graph_ready"] = False

with st.sidebar:
    st.header("1. Aircraft Config")
    reg = st.text_input("Registration", value="")
    
    engine_type = st.radio(
        "Engine Type", 
        ["Naturally Aspirated", "Turbocharged"], 
        on_change=reset_engine_mode
    )
    
    if engine_type == "Naturally Aspirated":
        rpm_drop_label = st.selectbox("RPM Correction Table", list(CORRECTION_MAP.keys()))
        factor = CORRECTION_MAP[rpm_drop_label]
    else:
        factor = 1.0 
        rpm_drop_label = "N/A"

is_turbo = (engine_type == "Turbocharged")

if is_turbo:
    c1, c2, c3 = st.columns(3)
    f_met = c1.file_uploader("Upload Max RPM METERED", type="csv", key="turbo_met")
    f_unm = c2.file_uploader("Upload Max RPM UNMETERED", type="csv", key="turbo_unm")
    f_idl = c3.file_uploader("Upload IDLE RPM", type="csv", key="turbo_idl")
    files = {"MET": f_met, "UNM": f_unm, "IDLE": f_idl}
else:
    c1, c2 = st.columns(2)
    f_na_max = c1.file_uploader("Upload Max RPM Data", type="csv", key="na_max")
    f_na_idl = c2.file_uploader("Upload Idle RPM Data", type="csv", key="na_idl")
    files = {"NA_MAX": f_na_max, "NA_IDLE": f_na_idl}

# --- 6. PROCESSING & DYNAMIC RENDERING ---
if st.button("Graph Uploaded Data"):
    st.session_state["graph_ready"] = True

if st.session_state.get("graph_ready"):
    current_charts = []
    try:
        if is_turbo:
            if files["MET"]:
                df = pd.read_csv(files["MET"])
                t, p = df.iloc[:, 0], df.iloc[:, 3]
                ps = savgol_filter(p, 9, 3)
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=t, y=p, name="Raw MET", line=dict(color="blue", width=2, dash="dot")))
                fig.add_trace(go.Scatter(x=t, y=ps, name="Smooth MET", line=dict(color="#00008B", width=3)))
                add_peak_marker(fig, t, ps, "Peak MET", "#00008B")
                apply_style(fig, f"Max RPM Metered Pressure - {reg}")
                current_charts.append(("Max RPM Metered", fig))

            if files["UNM"]:
                df = pd.read_csv(files["UNM"])
                t = df.iloc[:, 0]
                unm_col = [c for c in df.columns if "UNMETERED" in c.upper()][0]
                p, ps = df[unm_col], savgol_filter(df[unm_col], 9, 3)
                fig = go.Figure()
                fig.add_shape(type="rect", x0=t.iloc[0], x1=t.iloc[-1], y0=21, y1=24, fillcolor="#FFD700", opacity=0.3)
                add_label(fig, 22.5, "Turbo UNMETERED (21-24)", "#8B4513")
                fig.add_trace(go.Scatter(x=t, y=p, name="Raw UNM", line=dict(color="red", width=2, dash="dot")))
                fig.add_trace(go.Scatter(x=t, y=ps, name="Smooth UNM", line=dict(color="#8B0000", width=3)))
                add_peak_marker(fig, t, ps, "Peak UNM", "#8B0000")
                apply_style(fig, f"Max RPM Unmetered Pressure - {reg}")
                current_charts.append(("Max RPM Unmetered", fig))

            if files["IDLE"]:
                df = pd.read_csv(files["IDLE"])
                t = df.iloc[:, 0]
                unm_col = [c for c in df.columns if "UNMETERED" in c.upper()][0]
                p, ps = df[unm_col], savgol_filter(df[unm_col], 9, 3)
                fig = go.Figure()
                fig.add_shape(type="rect", x0=t.iloc[0], x1=t.iloc[-1], y0=7, y1=9, fillcolor="#FFD700", opacity=0.3)
                add_label(fig, 8, "Turbo Idle (7-9)", "#8B4513")
                fig.add_trace(go.Scatter(x=t, y=p, name="Raw Idle", line=dict(color="red", width=2, dash="dot")))
                fig.add_trace(go.Scatter(x=t, y=ps, name="Smooth Idle", line=dict(color="#8B0000", width=3)))
                add_peak_marker(fig, t, ps, "Min PSI", "#8B0000", is_min=True)
                apply_style(fig, f"Idle RPM Unmetered - {reg}")
                current_charts.append(("Idle RPM Unmetered", fig))
        else:
            if files["NA_MAX"]:
                df = pd.read_csv(files["NA_MAX"])
                t, u, m = df["Time (s)"], df["UNMETERED [PSI]"], df["METERED [PSI]"]
                us, ms = savgol_filter(u, 9, 3), savgol_filter(m, 9, 3)
                fig = go.Figure()
                fig.add_shape(type="rect", x0=t.iloc[0], x1=t.iloc[-1], y0=28, y1=30, fillcolor="#32CD32", opacity=0.3)
                
                ml, mh = 19.0 * factor, 21.3 * factor
                fig.add_shape(type="rect", x0=t.iloc[0], x1=t.iloc[-1], y0=ml, y1=mh, fillcolor="#00BFFF", opacity=0.3)
                add_label(fig, 29, "UNMETERED (28-30)", "#006400")
                
                metered_label_text = f"METERED ({rpm_drop_label}): {ml:.2f} - {mh:.2f} PSI"
                add_label(fig, (ml+mh)/2, metered_label_text, "#00008B")
                
                fig.add_trace(go.Scatter(x=t, y=u, name="Raw UNM", line=dict(color="red", width=2, dash="dot")))
                fig.add_trace(go.Scatter(x=t, y=m, name="Raw MET", line=dict(color="blue", width=2, dash="dot")))
                fig.add_trace(go.Scatter(x=t, y=us, name="Smooth UNM", line=dict(color="#8B0000", width=3)))
                fig.add_trace(go.Scatter(x=t, y=ms, name="Smooth MET", line=dict(color="#00008B", width=3)))
                add_peak_marker(fig, t, us, "Peak UNM", "#8B0000")
                add_peak_marker(fig, t, ms, "Peak MET", "#00008B")
                apply_style(fig, f"NA Max RPM Performance - {reg}")
                current_charts.append(("Max RPM Analysis", fig))

            if files["NA_IDLE"]:
                df = pd.read_csv(files["NA_IDLE"])
                t, p = df["Time (s)"], df["UNMETERED [PSI]"]
                ps = savgol_filter(p, 9, 3)
                fig = go.Figure()
                fig.add_shape(type="rect", x0=t.iloc[0], x1=t.iloc[-1], y0=8, y1=10, fillcolor="#32CD32", opacity=0.3)
                add_label(fig, 9, "NA Idle (8-10)", "#006400")
                fig.add_trace(go.Scatter(x=t, y=p, name="Raw Idle", line=dict(color="red", width=2, dash="dot")))
                fig.add_trace(go.Scatter(x=t, y=ps, name="Smooth Idle", line=dict(color="#8B0000", width=3)))
                add_peak_marker(fig, t, ps, "Min PSI", "#8B0000", is_min=True)
                apply_style(fig, f"Idle RPM Unmetered - {reg}")
                current_charts.append(("Idle RPM Unmetered", fig))

        for title, fig in current_charts:
            st.plotly_chart(fig, use_container_width=True)

        if current_charts and st.button("Generate Report from Current Graphs"):
            pdf = FPDF(orientation='L', unit='mm', format='A4')
            for title, fig in current_charts:
                img = fig.to_image(format="png", width=1200, height=700, scale=2)
                pdf.add_page(); pdf.set_font("Helvetica", "B", 16)
                pdf.cell(0, 10, f"{title} | {reg}", new_x="LMARGIN", new_y="NEXT")
                pdf.image(io.BytesIO(img), x=10, y=30, w=275)
            st.download_button("📥 Download PDF", data=bytes(pdf.output()), file_name=f"{reg}_Fuel_Report.pdf")

    except Exception as e:
        st.error(f"Please ensure correct mode is selected for uploaded data.")
