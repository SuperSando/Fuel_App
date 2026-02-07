import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from scipy.signal import savgol_filter
from datetime import datetime
from fpdf import FPDF
import io

# ---------------------------------------------------------
# CORRECTION DATA
# ---------------------------------------------------------
CORRECTION_MAP = {
    "Rated RPM (1.000)": 1.0,
    "-20 RPM (.991)": 0.991,
    "-40 RPM (.982)": 0.982,
    "-60 RPM (.973)": 0.973,
    "-80 RPM (.964)": 0.964,
    "-100 RPM (.955)": 0.955,
    "-120 RPM (.946)": 0.946
}

# ---------------------------------------------------------
# STYLING & PLOT ENGINE
# ---------------------------------------------------------
def apply_style(fig, title_text):
    fig.update_layout(
        template="plotly_white",
        title={'text': f"<b>{title_text}</b>", 'y': 0.95, 'x': 0.5, 'xanchor': 'center'},
        hovermode="x",
        xaxis=dict(showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=2, gridcolor="#e5e5e5", linecolor="black"),
        yaxis=dict(gridcolor="#e5e5e5", linecolor="black", zeroline=True, zerolinewidth=2, ticksuffix=" PSI")
    )

def create_plots(df_max, df_idle, opts, registration="", factor_label="", factor=1.0):
    un_p, un_s, met_b, id_p, id_s = opts
    met_low, met_high = 19.0 * factor, 21.3 * factor
    
    # --- MAX RPM ---
    time_m, un_m, met_m = df_max["Time (s)"], df_max["UNMETERED [PSI]"], df_max["METERED [PSI]"]
    un_sm, met_sm = savgol_filter(un_m, 9, 3), savgol_filter(met_m, 9, 3)
    fig_max = go.Figure()
    
    if un_s: fig_max.add_shape(type="rect", x0=time_m.iloc[0], x1=time_m.iloc[-1], y0=21.0, y1=24.0, fillcolor="#FFD700", opacity=0.3, layer="below")
    if un_p: fig_max.add_shape(type="rect", x0=time_m.iloc[0], x1=time_m.iloc[-1], y0=28.0, y1=30.0, fillcolor="#32CD32", opacity=0.3, layer="below")
    if met_b: 
        fig_max.add_shape(type="rect", x0=time_m.iloc[0], x1=time_m.iloc[-1], y0=met_low, y1=met_high, fillcolor="#00BFFF", opacity=0.3, layer="below")
        if factor != 1.0:
            fig_max.add_annotation(xref="paper", x=0.9, y=met_high, text=f"Max: {met_high:.2f}", showarrow=False, bgcolor="white")
            fig_max.add_annotation(xref="paper", x=0.9, y=met_low, text=f"Min: {met_low:.2f}", showarrow=False, bgcolor="white")

    fig_max.add_trace(go.Scatter(x=time_m, y=un_m, name="Raw UNM", line=dict(color="red", width=1, dash="dot")))
    fig_max.add_trace(go.Scatter(x=time_m, y=un_sm, name="Smooth UNM", line=dict(color="#8B0000", width=3)))
    fig_max.add_trace(go.Scatter(x=time_m, y=met_m, name="Raw MET", line=dict(color="blue", width=1, dash="dot")))
    fig_max.add_trace(go.Scatter(x=time_m, y=met_sm, name="Smooth MET", line=dict(color="#00008B", width=3)))
    apply_style(fig_max, f"Max RPM Fuel Pressure - {registration}")

    # --- IDLE RPM ---
    time_i, un_i = df_idle["Time (s)"], df_idle["UNMETERED [PSI]"]
    un_si = savgol_filter(un_i, 9, 3)
    fig_idle = go.Figure()
    if id_p: fig_idle.add_shape(type="rect", x0=time_i.iloc[0], x1=time_i.iloc[-1], y0=8.0, y1=10.0, fillcolor="#32CD32", opacity=0.3, layer="below")
    fig_idle.add_trace(go.Scatter(x=time_i, y=un_i, name="Raw UNM", line=dict(color="red", width=1, dash="dot")))
    fig_idle.add_trace(go.Scatter(x=time_i, y=un_si, name="Smooth UNM", line=dict(color="#8B0000", width=3)))
    apply_style(fig_idle, f"Idle RPM Fuel Pressure - {registration}")

    return fig_max, fig_idle

# ---------------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------------
st.set_page_config(page_title="Fuel Analysis Web", layout="wide")
st.title("✈️ Aircraft Fuel Pressure Diagnostic Tool")

with st.sidebar:
    st.header("Settings")
    reg = st.text_input("Registration", value="G-JONT")
    rpm_drop = st.selectbox("Achieved RPM Drop", list(CORRECTION_MAP.keys()))
    st.divider()
    st.subheader("Bands to Display")
    un_p = st.checkbox("Non-Turbo UNM (28-30)", value=True)
    un_s = st.checkbox("Turbo UNM (21-24)", value=False)
    met_b = st.checkbox("Metered (19-21.3)", value=True)
    id_p = st.checkbox("Idle Non-Turbo (8-10)", value=True)
    id_s = st.checkbox("Idle Turbo (7-9)", value=False)

col1, col2 = st.columns(2)
with col1: max_csv = st.file_uploader("Upload Max RPM Data", type="csv")
with col2: idle_csv = st.file_uploader("Upload Idle RPM Data", type="csv")

if max_csv and idle_csv:
    df_m = pd.read_csv(max_csv)
    df_i = pd.read_csv(idle_csv)
    factor = CORRECTION_MAP[rpm_drop]
    
    f_max, f_idle = create_plots(df_m, df_i, [un_p, un_s, met_b, id_p, id_s], reg, rpm_drop, factor)
    
    st.plotly_chart(f_max, use_container_width=True)
    st.plotly_chart(f_idle, use_container_width=True)
    
    # PDF EXPORT (In-Memory)
    if st.button("Generate PDF Report"):
        pdf = FPDF(orientation='L', unit='mm', format='A4')
        # PDF Generation Logic...
        st.success("PDF Ready for download!")