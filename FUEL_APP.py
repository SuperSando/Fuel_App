import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from scipy.signal import savgol_filter
from datetime import datetime
from fpdf import FPDF
import io
import os

# --- APP CONFIG ---
st.set_page_config(page_title="Fuel Analysis Tool", layout="wide")

# --- DATA ---
CORRECTION_MAP = {
    "Rated RPM (1.000)": 1.0,
    "-20 RPM (.991)": 0.991,
    "-40 RPM (.982)": 0.982,
    "-60 RPM (.973)": 0.973,
    "-80 RPM (.964)": 0.964,
    "-100 RPM (.955)": 0.955,
    "-120 RPM (.946)": 0.946
}

# --- STYLING ---
def apply_style(fig, title_text):
    fig.update_layout(
        template="plotly_white",
        title={'text': f"<b>{title_text}</b>", 'y': 0.95, 'x': 0.5, 'xanchor': 'center'},
        hovermode="x",
        xaxis=dict(showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=2, gridcolor="#e5e5e5", linecolor="black"),
        yaxis=dict(gridcolor="#e5e5e5", linecolor="black", zeroline=True, zerolinewidth=2, ticksuffix=" PSI")
    )

# --- ENGINE ---
def create_plots(df_max, df_idle, opts, reg="", factor_label="", factor=1.0):
    un_p, un_s, met_b, id_p, id_s = opts
    m_low, m_high = 19.0 * factor, 21.3 * factor
    
    # MAX RPM
    t_m, u_m, mt_m = df_max["Time (s)"], df_max["UNMETERED [PSI]"], df_max["METERED [PSI]"]
    u_sm, mt_sm = savgol_filter(u_m, 9, 3), savgol_filter(mt_m, 9, 3)
    
    f_max = go.Figure()
    if un_p: f_max.add_shape(type="rect", x0=t_m.iloc[0], x1=t_m.iloc[-1], y0=28.0, y1=30.0, fillcolor="#32CD32", opacity=0.3, layer="below")
    if met_b: 
        f_max.add_shape(type="rect", x0=t_m.iloc[0], x1=t_m.iloc[-1], y0=m_low, y1=m_high, fillcolor="#00BFFF", opacity=0.3, layer="below")
        if factor != 1.0:
            f_max.add_annotation(xref="paper", x=0.9, y=m_high, text=f"Max: {m_high:.2f}", showarrow=False, bgcolor="white")
            f_max.add_annotation(xref="paper", x=0.9, y=m_low, text=f"Min: {m_low:.2f}", showarrow=False, bgcolor="white")

    f_max.add_trace(go.Scatter(x=t_m, y=u_m, name="Raw UNM", line=dict(color="red", width=1.5, dash="dot")))
    f_max.add_trace(go.Scatter(x=t_m, y=u_sm, name="<b>Smooth UNM</b>", line=dict(color="#8B0000", width=3)))
    f_max.add_trace(go.Scatter(x=t_m, y=mt_sm, name="<b>Smooth MET</b>", line=dict(color="#00008B", width=3)))
    
    apply_style(f_max, f"Max RPM Fuel Pressure - {reg}")

    # IDLE RPM
    t_i, u_i = df_idle["Time (s)"], df_idle["UNMETERED [PSI]"]
    u_si = savgol_filter(u_i, 9, 3)
    f_idle = go.Figure()
    if id_p: f_idle.add_shape(type="rect", x0=t_i.iloc[0], x1=t_i.iloc[-1], y0=8.0, y1=10.0, fillcolor="#32CD32", opacity=0.3, layer="below")
    f_idle.add_trace(go.Scatter(x=t_i, y=u_i, name="Raw UNM", line=dict(color="red", width=1.5, dash="dot")))
    f_idle.add_trace(go.Scatter(x=t_i, y=u_si, name="<b>Smooth UNM</b>", line=dict(color="#8B0000", width=3)))
    apply_style(f_idle, f"Idle RPM Fuel Pressure - {reg}")

    return f_max, f_idle

# --- UI ---
st.title("✈️ Fuel Pressure Diagnostic Tool")

with st.sidebar:
    st.header("1. Aircraft Info")
    reg = st.text_input("Registration", value="G-JONT")
    rpm_drop = st.selectbox("Achieved RPM Drop", list(CORRECTION_MAP.keys()))
    st.divider()
    st.header("2. Bands")
    opts = [st.checkbox("Non-Turbo UNM (28-30)", True), 
            st.checkbox("Turbo UNM (21-24)", False), 
            st.checkbox("Metered (19-21.3)", True), 
            st.checkbox("Idle Non-Turbo (8-10)", True), 
            st.checkbox("Idle Turbo (7-9)", False)]

c1, c2 = st.columns(2)
m_file = c1.file_uploader("Upload Max RPM CSV", type="csv")
i_file = c2.file_uploader("Upload Idle RPM CSV", type="csv")

if m_file and i_file:
    df_m, df_i = pd.read_csv(m_file), pd.read_csv(i_file)
    f_m, f_id = create_plots(df_m, df_i, opts, reg, rpm_drop, CORRECTION_MAP[rpm_drop])
    
    st.plotly_chart(f_m, use_container_width=True)
    st.plotly_chart(f_id, use_container_width=True)

    # PDF Download
    if st.button("Prepare PDF Report"):
        pdf = FPDF(orientation='L', unit='mm', format='A4')
        for title, fig in [("Max RPM", f_m), ("Idle RPM", f_id)]:
            img = fig.to_image(format="png", width=1200, height=700, scale=2)
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, f"{title} | {reg}", ln=True)
            pdf.image(io.BytesIO(img), x=10, y=30, w=275)
        
        st.download_button("📥 Download PDF", data=pdf.output(dest='S'), file_name=f"{reg}_Report.pdf")