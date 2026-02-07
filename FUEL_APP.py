import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from scipy.signal import savgol_filter
from datetime import datetime
from fpdf import FPDF
import io

# --- 1. CONFIGURATION (MUST BE FIRST) ---
st.set_page_config(page_title="Fuel Analysis Tool", layout="wide")

# --- 2. PASSWORD GATEKEEPER ---
def password_entered():
    if st.session_state["password"] == st.secrets["password"]:
        st.session_state["password_correct"] = True
        del st.session_state["password"] 
    else:
        st.session_state["password_correct"] = False

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔒 Hangar Access Required")
        st.text_input("Enter Access Key", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.title("🔒 Hangar Access Required")
        st.text_input("Enter Access Key", type="password", on_change=password_entered, key="password")
        st.error("😕 Access Denied. Please try again.")
        return False
    return True

if not check_password():
    st.stop() 

# --- 3. DATA & CORRECTION TABLES ---
CORRECTION_MAP = {
    "Rated RPM (1.000)": 1.0,
    "-20 RPM (.991)": 0.991,
    "-40 RPM (.982)": 0.982,
    "-60 RPM (.973)": 0.973,
    "-80 RPM (.964)": 0.964,
    "-100 RPM (.955)": 0.955,
    "-120 RPM (.946)": 0.946
}

# --- 4. STYLING & LABELS ---
def apply_high_contrast_style(fig, title_text):
    fig.update_layout(
        template="plotly_white",
        title={'text': f"<b>{title_text}</b>", 'y': 0.95, 'x': 0.5, 'xanchor': 'center', 'font': {'size': 22, 'color': '#000'}},
        hovermode="x",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=12, color="black")),
        margin=dict(l=70, r=70, t=110, b=70),
        xaxis=dict(showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=2, spikecolor="black", gridcolor="#e5e5e5", linecolor="black", linewidth=2, showgrid=True, title_text="<b>Time (s)</b>"),
        yaxis=dict(gridcolor="#e5e5e5", linecolor="black", linewidth=2, zeroline=True, zerolinewidth=2, zerolinecolor="black", ticksuffix=" PSI", showgrid=True, title_text="<b>Pressure (PSI)</b>")
    )

def add_high_vis_label(fig, y_val, label_text, label_color, x_pos=0.01):
    fig.add_annotation(
        xref="paper", x=x_pos, y=y_val, text=f"<b>{label_text}</b>",
        showarrow=False, font=dict(color=label_color, size=11),
        bgcolor="white", bordercolor=label_color, borderwidth=2, borderpad=6, xanchor="left"
    )

# --- 5. CORE PLOT ENGINE ---
def create_plots(df_max, df_idle, opts, registration="", factor_label="", factor=1.0):
    un_p, un_s, met_b, id_p, id_s = opts
    met_low, met_high = 19.0 * factor, 21.3 * factor
    
    # MAX RPM processing
    t_m, u_m, mt_m = df_max["Time (s)"], df_max["UNMETERED [PSI]"], df_max["METERED [PSI]"]
    u_sm, mt_sm = savgol_filter(u_m, 9, 3), savgol_filter(mt_m, 9, 3)
    
    fig_max = go.Figure()
    if un_s:
        fig_max.add_shape(type="rect", x0=t_m.iloc[0], x1=t_m.iloc[-1], y0=21.0, y1=24.0, fillcolor="#FFD700", opacity=0.3, layer="below", line_width=0)
        add_high_vis_label(fig_max, 22.5, "Turbo UNMETERED (21-24)", "#8B4513")
    if un_p:
        fig_max.add_shape(type="rect", x0=t_m.iloc[0], x1=t_m.iloc[-1], y0=28.0, y1=30.0, fillcolor="#32CD32", opacity=0.3, layer="below", line_width=0)
        add_high_vis_label(fig_max, 29.0, "Non-Turbo UNMETERED (28-30)", "#006400")
    if met_b:
        fig_max.add_shape(type="rect", x0=t_m.iloc[0], x1=t_m.iloc[-1], y0=met_low, y1=met_high, fillcolor="#00BFFF", opacity=0.3, layer="below", line_width=1, line_color="#00008B")
        add_high_vis_label(fig_max, (met_low+met_high)/2, f"METERED ({factor_label})", "#00008B")
        if factor != 1.0:
            add_high_vis_label(fig_max, met_high, f"Max: {met_high:.2f}", "#00008B", x_pos=0.88)
            add_high_vis_label(fig_max, met_low, f"Min: {met_low:.2f}", "#00008B", x_pos=0.88)

    # High-Vis Traces
    fig_max.add_trace(go.Scatter(x=t_m, y=u_m, name="Raw UNM", line=dict(color="red", width=2, dash="dot"), hoverinfo="none"))
    fig_max.add_trace(go.Scatter(x=t_m, y=mt_m, name="Raw MET", line=dict(color="blue", width=2, dash="dot"), hoverinfo="none"))
    fig_max.add_trace(go.Scatter(x=t_m, y=u_sm, name="<b>Smooth UNM</b>", line=dict(color="#8B0000", width=3)))
    fig_max.add_trace(go.Scatter(x=t_m, y=mt_sm, name="<b>Smooth MET</b>", line=dict(color="#00008B", width=3)))
    
    # Markers
    m_un, m_mt = u_sm.argmax(), mt_sm.argmax()
    fig_max.add_trace(go.Scatter(x=[t_m.iloc[m_un]], y=[u_sm[m_un]], mode="markers+text", name="Max Smooth UNM", text=[f"<b>{u_sm[m_un]:.2f}</b>"], textposition="top center", marker=dict(color="#8B0000", size=12, line=dict(width=2, color="white"))))
    fig_max.add_trace(go.Scatter(x=[t_m.iloc[m_mt]], y=[mt_sm[m_mt]], mode="markers+text", name="Max Smooth MET", text=[f"<b>{mt_sm[m_mt]:.2f}</b>"], textposition="top center", marker=dict(color="#00008B", size=12, line=dict(width=2, color="white"))))
    
    r_un, r_mt = u_m.argmax(), mt_m.argmax()
    fig_max.add_trace(go.Scatter(x=[t_m.iloc[r_un]], y=[u_m.iloc[r_un]], mode="markers+text", name="Max Raw UNM", text=[f"{u_m.iloc[r_un]:.2f}"], textposition="bottom center", marker=dict(color="red", size=10, symbol="circle-open")))
    fig_max.add_trace(go.Scatter(x=[t_m.iloc[r_mt]], y=[mt_m.iloc[r_mt]], mode="markers+text", name="Max Raw MET", text=[f"{mt_m.iloc[r_mt]:.2f}"], textposition="bottom center", marker=dict(color="blue", size=10, symbol="circle-open")))

    apply_high_contrast_style(fig_max, f"Max RPM Fuel Pressure - {registration}")

    # --- IDLE RPM ---
    t_i, u_i = df_idle["Time (s)"], df_idle["UNMETERED [PSI]"]
    u_si = savgol_filter(u_i, 9, 3)
    fig_idle = go.Figure()
    if id_p:
        fig_idle.add_shape(type="rect", x0=t_i.iloc[0], x1=t_i.iloc[-1], y0=8.0, y1=10.0, fillcolor="#32CD32", opacity=0.3, layer="below")
        add_high_vis_label(fig_idle, 9.0, "Non-Turbo Idle (8-10)", "#006400")

    fig_idle.add_trace(go.Scatter(x=t_i, y=u_i, name="Raw UNM", line=dict(color="red", width=2, dash="dot"), hoverinfo="none"))
    fig_idle.add_trace(go.Scatter(x=t_i, y=u_si, name="<b>Smooth UNM</b>", line=dict(color="#8B0000", width=3)))
    
    mi_un, mi_r = u_si.argmin(), u_i.argmin()
    fig_idle.add_trace(go.Scatter(x=[t_i.iloc[mi_un]], y=[u_si[mi_un]], mode="markers+text", name="Min Smooth UNM", text=[f"<b>{u_si[mi_un]:.2f}</b>"], textposition="top center", marker=dict(color="#8B0000", size=12, line=dict(width=2, color="white"))))
    fig_idle.add_trace(go.Scatter(x=[t_i.iloc[mi_r]], y=[u_i.iloc[mi_r]], mode="markers+text", name="Min Raw UNM", text=[f"{u_i.iloc[mi_r]:.2f}"], textposition="bottom center", marker=dict(color="red", size=10, symbol="circle-open")))

    apply_high_contrast_style(fig_idle, f"Idle RPM Fuel Pressure - {registration}")
    return fig_max, fig_idle

# --- 6. STREAMLIT UI ---
st.title("Fuel Pressure Diagnostic Tool")

with st.sidebar:
    st.header("1. Aircraft & Correction")
    reg = st.text_input("Registration", value="")
    rpm_drop = st.selectbox("Achieved RPM Drop", list(CORRECTION_MAP.keys()))
    st.divider()
    st.header("2. Analysis Options")
    un_p = st.checkbox("Non-Turbo UNM (28-30)", True)
    un_s = st.checkbox("Turbo UNM (21-24)", False)
    met_b = st.checkbox("Metered (19-21.3)", True)
    id_p = st.checkbox("Idle Non-Turbo (8-10)", True)
    id_s = st.checkbox("Idle Turbo (7-9)", False)

c1, c2 = st.columns(2)
m_file = c1.file_uploader("Upload Max RPM CSV", type="csv")
i_file = c2.file_uploader("Upload Idle RPM CSV", type="csv")

if m_file and i_file:
    df_m = pd.read_csv(m_file)
    df_i = pd.read_csv(i_file)
    
    f_m, f_id = create_plots(df_m, df_i, [un_p, un_s, met_b, id_p, id_s], reg, rpm_drop, CORRECTION_MAP[rpm_drop])
    
    st.plotly_chart(f_m, use_container_width=True)
    st.plotly_chart(f_id, use_container_width=True)

    if st.button("Generate PDF Report"):
        with st.spinner("Preparing PDF..."):
            pdf = FPDF(orientation='L', unit='mm', format='A4')
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            for title, fig in [("Max RPM", f_m), ("Idle RPM", f_id)]:
                # Use kaleido for static export
                img_bytes = fig.to_image(format="png", width=1200, height=700, scale=2)
                pdf.add_page()
                pdf.set_font("Helvetica", "B", 16)
                # Updated cell positioning to remove deprecation warnings
                pdf.cell(0, 10, f"{title} | {reg}", new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", "", 10)
                pdf.cell(0, 10, f"Condition: {rpm_drop} | Generated: {ts}", new_x="LMARGIN", new_y="NEXT")
                pdf.image(io.BytesIO(img_bytes), x=10, y=35, w=275)
            
            # CRITICAL FIX: Cast bytearray to bytes for Streamlit download button
            st.download_button(
                label="📥 Download PDF Report", 
                data=bytes(pdf.output()), 
                file_name=f"{reg}_Report.pdf", 
                mime="application/pdf"
            )
