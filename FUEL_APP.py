import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from scipy.signal import savgol_filter
from datetime import datetime
from fpdf import FPDF
import io
# --- PASSWORD PROTECTION ---
def check_password():
    """Returns True if the user had the correct password."""
    if "password_correct" not in st.session_state:
        # First run, show input for password
        st.text_input("Enter Hangar Access Key", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error
        st.text_input("Enter Hangar Access Key", type="password", on_change=password_entered, key="password")
        st.error("😕 Access Denied")
        return False
    else:
        # Password correct
        return True

def password_entered():
    """Checks whether a password entered by the user is correct."""
    if st.session_state["password"] == st.secrets["password"]:
        st.session_state["password_correct"] = True
        del st.session_state["password"]  # don't store password
    else:
        st.session_state["password_correct"] = False

if not check_password():
    st.stop()  # Stop execution so the rest of the app doesn't run

# --- THE REST OF YOUR APP CODE STARTS HERE ---
st.title("Fuel Pressure Diagnostic Tool")
# ... (rest of the script)

# --- APP CONFIG ---
st.set_page_config(page_title="Fuel Analysis Tool", layout="wide")

# --- CORRECTION DATA ---
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
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=70, r=70, t=110, b=70),
        xaxis=dict(showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=2, gridcolor="#e5e5e5", linecolor="black", title_text="Time (s)"),
        yaxis=dict(gridcolor="#e5e5e5", linecolor="black", zeroline=True, zerolinewidth=2, ticksuffix=" PSI", title_text="Pressure (PSI)")
    )

def add_vis_label(fig, y_val, label_text, label_color, x_pos=0.01):
    fig.add_annotation(
        xref="paper", x=x_pos, y=y_val, text=f"<b>{label_text}</b>",
        showarrow=False, font=dict(color=label_color, size=11),
        bgcolor="white", bordercolor=label_color, borderwidth=2, borderpad=6, xanchor="left"
    )

# --- CORE ENGINE ---
def create_plots(df_max, df_idle, opts, reg="", factor_label="", factor=1.0):
    un_p, un_s, met_b, id_p, id_s = opts
    m_low, m_high = 19.0 * factor, 21.3 * factor
    
    # --- MAX RPM ---
    t_m, u_m, mt_m = df_max["Time (s)"], df_max["UNMETERED [PSI]"], df_max["METERED [PSI]"]
    u_sm, mt_sm = savgol_filter(u_m, 9, 3), savgol_filter(mt_m, 9, 3)
    
    f_max = go.Figure()
    
    # Restored Corrected Bands
    if un_s:
        f_max.add_shape(type="rect", x0=t_m.iloc[0], x1=t_m.iloc[-1], y0=21.0, y1=24.0, fillcolor="#FFD700", opacity=0.3, layer="below", line_width=0)
        add_vis_label(f_max, 22.5, "Turbo UNMETERED (21-24)", "#8B4513")
    if un_p:
        f_max.add_shape(type="rect", x0=t_m.iloc[0], x1=t_m.iloc[-1], y0=28.0, y1=30.0, fillcolor="#32CD32", opacity=0.3, layer="below", line_width=0)
        add_vis_label(f_max, 29.0, "Non-Turbo UNMETERED (28-30)", "#006400")
    if met_b: 
        f_max.add_shape(type="rect", x0=t_m.iloc[0], x1=t_m.iloc[-1], y0=m_low, y1=m_high, fillcolor="#00BFFF", opacity=0.3, layer="below", line_width=1, line_color="#00008B")
        add_vis_label(f_max, (m_low+m_high)/2, f"METERED ({factor_label})", "#00008B")
        if factor != 1.0:
            add_vis_label(f_max, m_high, f"Max: {m_high:.2f}", "#00008B", x_pos=0.88)
            add_vis_label(f_max, m_low, f"Min: {m_low:.2f}", "#00008B", x_pos=0.88)

    # Restored Raw & Smooth Traces
    f_max.add_trace(go.Scatter(x=t_m, y=u_m, name="Raw UNM", line=dict(color="red", width=2, dash="dot"), hoverinfo="none"))
    f_max.add_trace(go.Scatter(x=t_m, y=mt_m, name="Raw MET", line=dict(color="blue", width=2, dash="dot"), hoverinfo="none"))
    f_max.add_trace(go.Scatter(x=t_m, y=u_sm, name="<b>Smooth UNM</b>", line=dict(color="#8B0000", width=3)))
    f_max.add_trace(go.Scatter(x=t_m, y=mt_sm, name="<b>Smooth MET</b>", line=dict(color="#00008B", width=3)))
    
    # Restored Peak Markers
    m_un, m_mt = u_sm.argmax(), mt_sm.argmax()
    f_max.add_trace(go.Scatter(x=[t_m.iloc[m_un]], y=[u_sm[m_un]], mode="markers+text", name="Max Smooth UNM", text=[f"<b>{u_sm[m_un]:.2f}</b>"], textposition="top center", marker=dict(color="#8B0000", size=12, line=dict(width=2, color="white"))))
    f_max.add_trace(go.Scatter(x=[t_m.iloc[m_mt]], y=[mt_sm[m_mt]], mode="markers+text", name="Max Smooth MET", text=[f"<b>{mt_sm[m_mt]:.2f}</b>"], textposition="top center", marker=dict(color="#00008B", size=12, line=dict(width=2, color="white"))))
    
    r_un, r_mt = u_m.argmax(), mt_m.argmax()
    f_max.add_trace(go.Scatter(x=[t_m.iloc[r_un]], y=[u_m.iloc[r_un]], mode="markers+text", name="Max Raw UNM", text=[f"{u_m.iloc[r_un]:.2f}"], textposition="bottom center", marker=dict(color="red", size=10, symbol="circle-open")))
    f_max.add_trace(go.Scatter(x=[t_m.iloc[r_mt]], y=[mt_m.iloc[r_mt]], mode="markers+text", name="Max Raw MET", text=[f"{mt_m.iloc[r_mt]:.2f}"], textposition="bottom center", marker=dict(color="blue", size=10, symbol="circle-open")))

    apply_style(f_max, f"Max RPM Fuel Pressure - {reg}")

    # --- IDLE RPM ---
    t_i, u_i = df_idle["Time (s)"], df_idle["UNMETERED [PSI]"]
    u_si = savgol_filter(u_i, 9, 3)
    f_idle = go.Figure()
    
    if id_p: 
        f_idle.add_shape(type="rect", x0=t_i.iloc[0], x1=t_i.iloc[-1], y0=8.0, y1=10.0, fillcolor="#32CD32", opacity=0.3, layer="below")
        add_vis_label(f_idle, 9.0, "Non-Turbo Idle (8-10)", "#006400")

    f_idle.add_trace(go.Scatter(x=t_i, y=u_i, name="Raw UNM", line=dict(color="red", width=2, dash="dot"), hoverinfo="none"))
    f_idle.add_trace(go.Scatter(x=t_i, y=u_si, name="<b>Smooth UNM</b>", line=dict(color="#8B0000", width=3)))
    
    mi_un, mi_r = u_si.argmin(), u_i.argmin()
    f_idle.add_trace(go.Scatter(x=[t_i.iloc[mi_un]], y=[u_si[mi_un]], mode="markers+text", name="Min Smooth UNM", text=[f"<b>{u_si[mi_un]:.2f}</b>"], textposition="top center", marker=dict(color="#8B0000", size=12, line=dict(width=2, color="white"))))
    f_idle.add_trace(go.Scatter(x=[t_i.iloc[mi_r]], y=[u_i.iloc[mi_r]], mode="markers+text", name="Min Raw UNM", text=[f"{u_i.iloc[mi_r]:.2f}"], textposition="bottom center", marker=dict(color="red", size=10, symbol="circle-open")))

    apply_style(f_idle, f"Idle RPM Fuel Pressure - {reg}")

    return f_max, f_idle

# --- STREAMLIT UI ---
st.title("✈️ Fuel Pressure Diagnostic Tool")

with st.sidebar:
    st.header("1. Aircraft Info")
    reg = st.text_input("Registration", value="")
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
    df_m = pd.read_csv(m_file)
    df_i = pd.read_csv(i_file)
    
    f_m, f_id = create_plots(df_m, df_i, opts, reg, rpm_drop, CORRECTION_MAP[rpm_drop])
    
    st.plotly_chart(f_m, use_container_width=True)
    st.plotly_chart(f_id, use_container_width=True)

    if st.button("Generate PDF Report"):
        pdf = FPDF(orientation='L', unit='mm', format='A4')
        for title, fig in [("Max RPM", f_m), ("Idle RPM", f_id)]:
            img = fig.to_image(format="png", width=1200, height=700, scale=2)
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, f"{title} | {reg}", ln=True)
            pdf.image(io.BytesIO(img), x=10, y=30, w=275)
        
        st.download_button("📥 Download PDF", data=pdf.output(), file_name=f"{reg}_Report.pdf", mime="application/pdf")



