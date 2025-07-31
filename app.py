import streamlit as st
import pandas as pd
import numpy as np
import math
import matplotlib.pyplot as plt
from fpdf import FPDF
from io import BytesIO

st.set_page_config(page_title="DME/CDFA Descent Planner", layout="centered")

# Utility: Calculate slant-range DME distance
def slant_range_dme(horizontal_distance_nm, altitude_ft):
    return math.sqrt(horizontal_distance_nm**2 + (altitude_ft / 6076.12)**2)

# GP angle (°) = arctan(height / distance)
def calculate_gp_angle(thr_elevation, tod_altitude, dme_distance_nm):
    height_diff_ft = tod_altitude - thr_elevation
    return math.degrees(math.atan(height_diff_ft / (dme_distance_nm * 6076.12)))

def round_to_10(x):
    return int(round(x / 10.0) * 10)

def generate_dme_table(thr_elevation, tod_altitude, dme_at_thr, mda, sdf_inputs):
    total_distance = dme_at_thr
    distances = np.linspace(dme_at_thr, 0.5, 8)

    gp_angle = calculate_gp_angle(thr_elevation, tod_altitude, total_distance)

    table = []
    for dme in distances:
        slant_dme = slant_range_dme(dme, tod_altitude - thr_elevation)
        altitude = thr_elevation + math.tan(math.radians(gp_angle)) * slant_dme * 6076.12
        altitude = max(altitude, mda)
        label = ""
        for i, sdf in enumerate(sdf_inputs):
            if sdf and abs(dme - sdf["Distance"]) < 0.15:
                label = f"SDF{i+1}"
                altitude = sdf["Altitude"]
        if abs(dme - dme_at_thr) < 0.15:
            label = "FAF"
        elif dme < 0.7:
            label = "MAPt"
        table.append({"DME": round(dme, 2), "Altitude": int(altitude), "Fix": label})
    return table, gp_angle

def generate_rod_table(gp_angle_deg, faf_mapt_distance):
    ground_speeds = [80, 100, 120, 140, 160]
    rod_table = []
    for gs in ground_speeds:
        rod = round_to_10(gs * 101.3 * math.tan(math.radians(gp_angle_deg)))
        time_min = faf_mapt_distance / gs * 60
        rod_table.append({"GS": gs, "ROD (ft/min)": rod, "Time FAF→MAPt": f"{int(time_min)}:{int((time_min%1)*60):02d}"})
    return rod_table

# PDF generation
def create_pdf(dme_df, rod_df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=14)
    pdf.cell(200, 10, txt="DME/CDFA Descent Planner Report", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.ln(10)

    # DME Table
    pdf.cell(200, 10, txt="DME Table (8-Point Descent Profile):", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.cell(60, 10, "DME (NM)", 1)
    pdf.cell(60, 10, "Altitude (ft)", 1)
    pdf.cell(60, 10, "Fix", 1)
    pdf.ln()
    for row in dme_df:
        pdf.cell(60, 10, str(row["DME"]), 1)
        pdf.cell(60, 10, str(row["Altitude"]), 1)
        pdf.cell(60, 10, row["Fix"], 1)
        pdf.ln()

    # ROD Table
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="ROD Table (FAF to MAPt):", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.cell(40, 10, "GS (kts)", 1)
    pdf.cell(60, 10, "ROD (ft/min)", 1)
    pdf.cell(60, 10, "Time FAF→MAPt", 1)
    pdf.ln()
    for row in rod_df:
        pdf.cell(40, 10, str(row["GS"]), 1)
        pdf.cell(60, 10, str(row["ROD (ft/min)"]), 1)
        pdf.cell(60, 10, row["Time FAF→MAPt"], 1)
        pdf.ln()

    return pdf.output(dest='S').encode('latin1', errors='replace')

# Streamlit UI
st.title("🛬 DME/CDFA Descent Planner Tool")

col1, col2 = st.columns(2)
with col1:
    thr_elevation = st.number_input("Threshold Elevation (ft)", value=150)
    tod_altitude = st.number_input("Top of Descent Altitude (ft)", value=3000)
    mda = st.number_input("Minimum Descent Altitude (MDA) (ft)", value=670)
with col2:
    dme_at_thr = st.number_input("DME Reading at Threshold (NM)", value=5.5)
    faf_mapt_distance = st.number_input("FAF to MAPt Distance (NM)", value=5.5)

sdf_inputs = []
for i in range(6):
    with st.expander(f"Optional Step-Down Fix SDF{i+1}"):
        alt = st.number_input(f"SDF{i+1} Altitude (ft)", value=0, key=f"sdf_alt_{i}")
        dist = st.number_input(f"SDF{i+1} Distance (NM)", value=0.0, key=f"sdf_dist_{i}")
        if alt > 0 and dist > 0:
            sdf_inputs.append({"Altitude": alt, "Distance": dist})
        else:
            sdf_inputs.append(None)

if st.button("Generate Descent Plan"):
    dme_table, gp_angle = generate_dme_table(thr_elevation, tod_altitude, dme_at_thr, mda, sdf_inputs)
    rod_table = generate_rod_table(gp_angle, faf_mapt_distance)

    st.subheader("DME Descent Table")
    st.table(pd.DataFrame(dme_table))

    st.subheader("ROD Table (FAF to MAPt)")
    st.table(pd.DataFrame(rod_table))

    # Chart
    fig, ax = plt.subplots()
    ax.plot([p["DME"] for p in dme_table], [p["Altitude"] for p in dme_table], marker='o', color='blue')
    ax.axhline(y=mda, color='red', linestyle='--', label='MDA')
    for p in dme_table:
        ax.annotate(p["Fix"], (p["DME"], p["Altitude"]), textcoords="offset points", xytext=(0,10), ha='center')
    ax.set_xlabel("DME (NM)")
    ax.set_ylabel("Altitude (ft)")
    ax.set_title("CDFA Profile View")
    ax.invert_xaxis()
    ax.invert_yaxis()
    st.pyplot(fig)

    # Export
    pdf_bytes = create_pdf(dme_table, rod_table)
    st.download_button("📄 Download PDF Report", data=pdf_bytes, file_name="CDFA_Descent_Report.pdf")

    # CSV Export
    dme_df = pd.DataFrame(dme_table)
    rod_df = pd.DataFrame(rod_table)
    csv_dme = dme_df.to_csv(index=False).encode('utf-8')
    csv_rod = rod_df.to_csv(index=False).encode('utf-8')
    st.download_button("📁 Download DME Table (CSV)", data=csv_dme, file_name="DME_Table.csv")
    st.download_button("📁 Download ROD Table (CSV)", data=csv_rod, file_name="ROD_Table.csv")


