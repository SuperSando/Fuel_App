import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from scipy.signal import savgol_filter
from datetime import datetime
from fpdf import FPDF
import io

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Fuel Analysis Tool", layout="wide")

st.markdown("""
    <style>
        .stApp { background-color: white !important; }
        section[data-testid="stSidebar"] { background-color: #f0f2f6 !important; }
        p, h1, h2, h3, label { color: #31333f !important; }
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

# --- 5. UI LAYOUT ---
try: st.sidebar.image("logo.png", width=180)
except: pass

st.title("Aviation Fuel Pressure Diagnostic Tool")

with st.sidebar:
    st.header("1. Aircraft Config")
    reg = st.text_input("Registration", value="")
    engine_type = st.radio("Engine Type", ["Naturally Aspirated", "Turbocharged"])
    rpm_drop = st.selectbox("RPM Correction Table", list(CORRECTION_MAP.keys()))
    factor = CORRECTION_MAP[rpm_drop]

is_turbo = (engine_type == "Turbocharged")
charts = []

if is_turbo:
    c1, c2, c3 = st.columns(3)
    f_met = c1.file_uploader("Upload Max RPM METERED", type="csv")
    f_unm = c2.file_uploader("Upload Max RPM UNMETERED", type="csv")
    f_idl = c3.file_uploader("Upload IDLE RPM", type="csv")

    if f_met and f_unm and f_idl:
        try:
            # 1. Max Metered
            df1 = pd.read_csv(f_met)
            t1, p1 = df1.iloc[:, 0], df1.iloc[:, 3]
            ps1 = savgol_filter(p1, 9, 3)
            fig1 = go.Figure()
            m_low, m_high = 19.0 * factor, 21.3 * factor
            fig1.add_shape(type="rect", x0=t1.iloc[0], x1=t1.iloc[-1], y0=m_low, y1=m_high, fillcolor="#00BFFF", opacity=0.3)
            add_label(fig1, (m_low+m_high)/2, f"METERED ({rpm_drop})", "#00008B")
            fig1.add_trace(go.Scatter(x=t1, y=p1, name="Raw MET", line=dict(color="blue", width=2, dash="dot")))
            fig1.add_trace(go.Scatter(x=t1, y=ps1, name="<b>Smooth MET</b>", line=dict(color="#00008B", width=3)))
            add_peak_marker(fig1, t1, ps1, "Peak MET", "#00008B")
            apply_style(fig1, f"Max RPM Metered Pressure - {reg}")
            charts.append(("Max RPM Metered", fig1))

            # 2. Max Unmetered
            df2 = pd.read_csv(f_unm)
            t2 = df2.iloc[:, 0]
            unm_col = [c for c in df2.columns if "UNMETERED" in c.upper() or "DIFFERENTIAL" in c.upper()][0]
            p2, ps2 = df2[unm_col], savgol_filter(df2[unm_col], 9, 3)
            fig2 = go.Figure()
            fig2.add_shape(type="rect", x0=t2.iloc[0], x1=t2.iloc[-1], y0=21.0, y1=24.0, fillcolor="#FFD700", opacity=0.3)
            add_label(fig2, 22.5, "Turbo UNMETERED (21-24)", "#8B4513")
            fig2.add_trace(go.Scatter(x=t2, y=p2, name="Raw UNM", line=dict(color="red", width=2, dash="dot")))
            fig2.add_trace(go.Scatter(x=t2, y=ps2, name="<b>Smooth UNM</b>", line=dict(color="#8B0000", width=3)))
            add_peak_marker(fig2, t2, ps2, "Peak UNM", "#8B0000")
            apply_style(fig2, f"Max RPM Unmetered Pressure - {reg}")
            charts.append(("Max RPM Unmetered", fig2))

            # 3. Idle
            df3 = pd.read_csv(f_idl)
            t3, p3 = df3.iloc[:, 0], df3.iloc[:, 3]
            ps3 = savgol_filter(p3, 9, 3)
            fig3 = go.Figure()
            fig3.add_shape(type="rect", x0=t3.iloc[0], x1=t3.iloc[-1], y0=7.0, y1=9.0, fillcolor="#FFD700", opacity=0.3)
            add_label(fig3, 8.0, "Turbo Idle (7-9)", "#8B4513")
            fig3.add_trace(go.Scatter(x=t3, y=p3, name="Raw Idle", line=dict(color="red", width=2, dash="dot")))
            fig3.add_trace(go.Scatter(x=t3, y=ps3, name="<b>Smooth Idle</b>", line=dict(color="#8B0000", width=3)))
            add_peak_marker(fig3, t3, ps3, "Min PSI", "#8B0000", is_min=True)
            apply_style(fig3, f"Idle RPM Check - {reg}")
            charts.append(("Idle RPM", fig3))
        except: st.warning("⚠️ Turbo Data Mismatch.")

else:
    c1, c2 = st.columns(2)
    f_max, f_idl = c1.file_uploader("Upload Max RPM Data", type="csv"), c2.file_uploader("Upload Idle RPM Data", type="csv")

    if f_max and f_idl:
        try:
            df1, df2 = pd.read_csv(f_max), pd.read_csv(f_idl)
            t1, u1, m1 = df1["Time (s)"], df1["UNMETERED [PSI]"], df1["METERED [PSI]"]
            us1, ms1 = savgol_filter(u1, 9, 3), savgol_filter(m1, 9, 3)
            fig1 = go.Figure()
            fig1.add_shape(type="rect", x0=t1.iloc[0], x1=t1.iloc[-1], y0=28, y1=30, fillcolor="#32CD32", opacity=0.3)
            ml, mh = 19.0*factor, 21.3*factor
            fig1.add_shape(type="rect", x0=t1.iloc[0], x1=t1.iloc[-1], y0=ml, y1=mh, fillcolor="#00BFFF", opacity=0.3)
            fig1.add_trace(go.Scatter(x=t1, y=u1, name="Raw UNM", line=dict(color="red", width=2, dash="dot")))
            fig1.add_trace(go.Scatter(x=t1, y=m1, name="Raw MET", line=dict(color="blue", width=2, dash="dot")))
            fig1.add_trace(go.Scatter(x=t1, y=us1, name="Smooth UNM", line=dict(color="#8B0000", width=3)))
            fig1.add_trace(go.Scatter(x=t1, y=ms1, name="Smooth MET", line=dict(color="#00008B", width=3)))
            add_peak_marker(fig1, t1, us1, "Peak UNM", "#8B0000")
            add_peak_marker(fig1, t1, ms1, "Peak MET", "#00008B")
            apply_style(fig1, f"NA Max RPM Performance - {reg}")
            charts.append(("Max RPM Analysis", fig1))

            t2, p2 = df2["Time (s)"], df2["UNMETERED [PSI]"]
            ps2 = savgol_filter(p2, 9, 3)
            fig2 = go.Figure()
            fig2.add_shape(type="rect", x0=t2.iloc[0], x1=t2.iloc[-1], y0=8, y1=10, fillcolor="#32CD32", opacity=0.3)
            fig2.add_trace(go.Scatter(x=t2, y=p2, name="Raw Idle", line=dict(color="red", width=2, dash="dot")))
            fig2.add_trace(go.Scatter(x=t2, y=ps2, name="Smooth Idle", line=dict(color="#8B0000", width=3)))
            add_peak_marker(fig2, t2, ps2, "Min PSI", "#8B0000", is_min=True)
            apply_style(fig2, f"NA Idle Check - {reg}")
            charts.append(("Idle RPM", fig2))
        except: st.warning("⚠️ NA Headers Mismatch.")

# --- 6. RENDER ---
for title, fig in charts: st.plotly_chart(fig, use_container_width=True)

if charts and st.button("Generate Airworthiness Report"):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    for title, fig in charts:
        img = fig.to_image(format="png", width=1200, height=700, scale=2)
        pdf.add_page(); pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, f"{title} | {reg}", new_x="LMARGIN", new_y="NEXT")
        pdf.image(io.BytesIO(img), x=10, y=30, w=275)
    st.download_button("📥 Download PDF", data=bytes(pdf.output()), file_name=f"{reg}_Fuel_Report.pdf")
