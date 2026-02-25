import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from scipy.signal import savgol_filter
from datetime import datetime
from fpdf import FPDF
import io

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Fuel Analysis Tool", layout="wide")

# --- FORCE LIGHT MODE CSS ---
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
    else:
        st.session_state["password_correct"] = False

def check_password():
    if "password_correct" not in st.session_state:
        try: st.image("logo.png", width=200)
        except: pass
        st.title("🔒 Hangar Access Required")
        st.text_input("Enter Access Key", type="password", on_change=password_entered, key="password")
        return False
    return True

if not check_password():
    st.stop() 

# --- 3. CONSTANTS ---
CORRECTION_MAP = {
    "Rated RPM (1.000)": 1.0, "-20 RPM (.991)": 0.991, "-40 RPM (.982)": 0.982,
    "-60 RPM (.973)": 0.973, "-80 RPM (.964)": 0.964, "-100 RPM (.955)": 0.955, "-120 RPM (.946)": 0.946
}

# --- 4. STYLING HELPERS ---
def apply_high_contrast_style(fig, title_text):
    fig.update_layout(
        template="plotly_white", paper_bgcolor="white", plot_bgcolor="white",
        title={'text': f"<b>{title_text}</b>", 'y': 0.95, 'x': 0.5, 'xanchor': 'center', 'font': {'size': 22, 'color': '#000'}},
        hovermode="x", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=12, color="black")),
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

# --- 5. CHARTING ENGINE ---
def generate_charts(df_max, df_idle, is_turbo, reg, factor_label, factor):
    try:
        f_max = go.Figure()
        met_low, met_high = 19.0 * factor, 21.3 * factor
        
        if is_turbo:
            t_m, p_m = df_max.iloc[:, 0], df_max.iloc[:, 3]
            p_sm = savgol_filter(p_m, 9, 3)
            f_max.add_shape(type="rect", x0=t_m.iloc[0], x1=t_m.iloc[-1], y0=21.0, y1=24.0, fillcolor="#FFD700", opacity=0.3, layer="below", line_width=0)
            add_high_vis_label(f_max, 22.5, "Turbo UNMETERED (21-24)", "#8B4513")
            f_max.add_trace(go.Scatter(x=t_m, y=p_m, name="Raw FUEL PRESSURE", line=dict(color="blue", width=2, dash="dot"), hoverinfo="none"))
            f_max.add_trace(go.Scatter(x=t_m, y=p_sm, name="<b>Smooth FUEL PRESSURE</b>", line=dict(color="#00008B", width=3)))
            m_pt = p_sm.argmax()
            f_max.add_trace(go.Scatter(x=[t_m.iloc[m_pt]], y=[p_sm[m_pt]], mode="markers+text", name="Peak PSI", text=[f"<b>{p_sm[m_pt]:.2f}</b>"], textposition="top center", marker=dict(color="#00008B", size=12, line=dict(width=2, color="white"))))
        else:
            t_m = df_max["Time (s)"]
            u_m, mt_m = df_max["UNMETERED [PSI]"], df_max["METERED [PSI]"]
            u_sm, mt_sm = savgol_filter(u_m, 9, 3), savgol_filter(mt_m, 9, 3)
            f_max.add_shape(type="rect", x0=t_m.iloc[0], x1=t_m.iloc[-1], y0=28.0, y1=30.0, fillcolor="#32CD32", opacity=0.3, layer="below", line_width=0)
            add_high_vis_label(f_max, 29.0, "Non-Turbo UNMETERED (28-30)", "#006400")
            f_max.add_trace(go.Scatter(x=t_m, y=u_m, name="Raw UNM", line=dict(color="red", width=2, dash="dot"), hoverinfo="none"))
            f_max.add_trace(go.Scatter(x=t_m, y=mt_m, name="Raw MET", line=dict(color="blue", width=2, dash="dot"), hoverinfo="none"))
            f_max.add_trace(go.Scatter(x=t_m, y=u_sm, name="<b>Smooth UNM</b>", line=dict(color="#8B0000", width=3)))
            f_max.add_trace(go.Scatter(x=t_m, y=mt_sm, name="<b>Smooth MET</b>", line=dict(color="#00008B", width=3)))
            un_pt, mt_pt = u_sm.argmax(), mt_sm.argmax()
            f_max.add_trace(go.Scatter(x=[t_m.iloc[un_pt]], y=[u_sm[un_pt]], mode="markers+text", name="Peak UNM", text=[f"<b>{u_sm[un_pt]:.2f}</b>"], textposition="top center", marker=dict(color="#8B0000", size=12, line=dict(width=2, color="white"))))
            f_max.add_trace(go.Scatter(x=[t_m.iloc[mt_pt]], y=[mt_sm[mt_pt]], mode="markers+text", name="Peak MET", text=[f"<b>{mt_sm[mt_pt]:.2f}</b>"], textposition="top center", marker=dict(color="#00008B", size=12, line=dict(width=2, color="white"))))

        f_max.add_shape(type="rect", x0=t_m.iloc[0], x1=t_m.iloc[-1], y0=met_low, y1=met_high, fillcolor="#00BFFF", opacity=0.3, layer="below", line_width=1, line_color="#00008B")
        add_high_vis_label(f_max, (met_low+met_high)/2, f"METERED ({factor_label})", "#00008B")
        apply_high_contrast_style(f_max, f"Max RPM Analysis - {reg}")

        # IDLE PLOT
        f_idle = go.Figure()
        if is_turbo:
            t_i, p_i = df_idle.iloc[:, 0], df_idle.iloc[:, 3]
            p_si = savgol_filter(p_i, 9, 3)
            f_idle.add_shape(type="rect", x0=t_i.iloc[0], x1=t_i.iloc[-1], y0=7.0, y1=9.0, fillcolor="#FFD700", opacity=0.3, layer="below")
            add_high_vis_label(f_idle, 8.0, "Turbo Idle (7-9)", "#8B4513")
            f_idle.add_trace(go.Scatter(x=t_i, y=p_i, name="Raw FUEL PRESSURE", line=dict(color="red", width=2, dash="dot")))
            f_idle.add_trace(go.Scatter(x=t_i, y=p_si, name="<b>Smooth FUEL PRESSURE</b>", line=dict(color="#8B0000", width=3)))
            i_pt, val = p_si.argmin(), p_si.min()
        else:
            t_i, unm_i = df_idle["Time (s)"], df_idle["UNMETERED [PSI]"]
            unm_si = savgol_filter(unm_i, 9, 3)
            f_idle.add_shape(type="rect", x0=t_i.iloc[0], x1=t_i.iloc[-1], y0=8.0, y1=10.0, fillcolor="#32CD32", opacity=0.3, layer="below")
            add_high_vis_label(f_idle, 9.0, "Non-Turbo Idle (8-10)", "#006400")
            f_idle.add_trace(go.Scatter(x=t_i, y=unm_i, name="Raw Unmetered", line=dict(color="red", width=2, dash="dot")))
            f_idle.add_trace(go.Scatter(x=t_i, y=unm_si, name="<b>Smooth Unmetered</b>", line=dict(color="#8B0000", width=3)))
            i_pt, val = unm_si.argmin(), unm_si.min()

        f_idle.add_trace(go.Scatter(x=[t_i.iloc[i_pt]], y=[val], mode="markers+text", name="Min PSI", text=[f"<b>{val:.2f}</b>"], textposition="top center", marker=dict(color="#8B0000", size=12, line=dict(width=2, color="white"))))
        apply_high_contrast_style(f_idle, f"Idle RPM Check - {reg}")
        
        return f_max, f_idle

    except Exception:
        return None, None

# --- 6. UI ---
try: st.sidebar.image("logo.png", width=180)
except: pass

st.title("Aviation Fuel Pressure Diagnostic Tool")

with st.sidebar:
    st.header("1. Aircraft Config")
    reg = st.text_input("Registration", value="")
    engine_type = st.radio("Engine Type", ["Naturally Aspirated", "Turbocharged"])
    rpm_drop = st.selectbox("RPM Correction Table", list(CORRECTION_MAP.keys()))

c1, c2 = st.columns(2)
m_file = c1.file_uploader("Upload Max RPM CSV", type="csv")
i_file = c2.file_uploader("Upload Idle RPM CSV", type="csv")

if m_file and i_file:
    df_m, df_i = pd.read_csv(m_file), pd.read_csv(i_file)
    is_turbo = (engine_type == "Turbocharged")
    
    f_m, f_id = generate_charts(df_m, df_i, is_turbo, reg, rpm_drop, CORRECTION_MAP[rpm_drop])
    
    if f_m is None:
        st.warning(f"⚠️ **Data Not Recognized:** The uploaded file headers do not match the **{engine_type}** mode. Please check your selection or the CSV format.")
    else:
        st.plotly_chart(f_m, width="stretch")
        st.plotly_chart(f_id, width="stretch")

        if st.button("Generate Airworthiness Report (PDF)"):
            with st.spinner("Compiling Data..."):
                pdf = FPDF(orientation='L', unit='mm', format='A4')
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                for title, fig in [("Max Power Analysis", f_m), ("Idle Check", f_id)]:
                    img = fig.to_image(format="png", width=1200, height=700, scale=2)
                    pdf.add_page()
                    pdf.set_font("Helvetica", "B", 16)
                    pdf.cell(0, 10, f"{title} | {reg}", new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font("Helvetica", "", 10)
                    pdf.cell(0, 10, f"Generated: {ts} | Mode: {engine_type}", new_x="LMARGIN", new_y="NEXT")
                    pdf.image(io.BytesIO(img), x=10, y=35, w=275)
                st.download_button("📥 Download PDF Report", data=bytes(pdf.output()), file_name=f"{reg}_Fuel_Report.pdf", mime="application/pdf")
