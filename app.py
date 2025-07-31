import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math
from fpdf import FPDF
from io import BytesIO

def calculate_gp_gradient(faf_alt, mda, distance_nm):
    height_diff = faf_alt - mda
    if distance_nm > 0:
        angle_rad = math.atan(height_diff / (distance_nm * 6076.12))
        angle_deg = math.degrees(angle_rad)
        gradient_ft_per_nm = height_diff / distance_nm
        gradient_percent = (height_diff / (distance_nm * 6076.12)) * 100
    else:
        angle_deg = 0
        gradient_ft_per_nm = 0
        gradient_percent = 0
    return round(angle_deg, 2), round(gradient_ft_per_nm), round(gradient_percent, 2)

def create_pdf(dme_table, rod_table):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, "DME/CDFA Descent Planner Report", ln=1, align="C")

    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 10, "DME Table", ln=1)

    pdf.set_font("Arial", "", 11)
    pdf.cell(40, 10, "Fix", 1)
    pdf.cell(40, 10, "Distance (NM)", 1)
    pdf.cell(40, 10, "Altitude (ft)", 1)
    pdf.cell(40, 10, "Type", 1)
    pdf.ln()
    for row in dme_table:
        pdf.cell(40, 10, row["Fix"], 1)
        pdf.cell(40, 10, f'{row["Distance"]:.2f}', 1)
        pdf.cell(40, 10, str(int(row["Altitude"])), 1)
        pdf.cell(40, 10, row["Type"], 1)
        pdf.ln()

    pdf.ln()
    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 10, "ROD Table", ln=1)

    pdf.set_font("Arial", "", 11)
    pdf.cell(50, 10, "Ground Speed (kt)", 1)
    pdf.cell(50, 10, "ROD (fpm)", 1)
    pdf.cell(50, 10, "Time FAF–MAPt (min)", 1)
    pdf.ln()
    for row in rod_table:
        pdf.cell(50, 10, str(row["GS"]), 1)
        pdf.cell(50, 10, str(row["ROD"]), 1)
        pdf.cell(50, 10, f'{row["Time(min)"]:.2f}', 1)
        pdf.ln()

    pdf_buffer = BytesIO()
pdf.output(pdf_buffer)
return pdf_buffer.getvalue()

def plot_profile(dme_table, mda):
    distances = [row["Distance"] for row in dme_table]
    altitudes = [row["Altitude"] for row in dme_table]
    labels = [row["Fix"] for row in dme_table]

    fig, ax = plt.subplots()
    ax.plot(distances, altitudes, marker='o', linestyle='-', color='blue')
    ax.axhline(mda, color='red', linestyle='--', label='MDA')
    for i, label in enumerate(labels):
        ax.text(distances[i], altitudes[i] + 50, label, ha='center', fontsize=8)
    ax.set_title("CDFA Profile View")
    ax.set_xlabel("Distance (NM)")
    ax.set_ylabel("Altitude (ft)")
    ax.grid(True)
    ax.legend()
    return fig

st.set_page_config(page_title="DME/CDFA Descent Planner", layout="centered")
st.title("🛬 DME/CDFA Descent Planner Tool")

col1, col2 = st.columns(2)
with col1:
    elevation = st.number_input("Runway Threshold Elevation (ft)", value=100)
    mda = st.number_input("MDA (Minimum Descent Altitude)", value=1200)
    tod_distance = st.number_input("Top of Descent Distance (from THR, NM)", value=7.0, step=0.1)
    dme_at_thr = st.number_input("DME Distance at THR (NM)", value=0.5, step=0.1)
with col2:
    lat = st.text_input("Latitude", value="N00°00.00'")
    lon = st.text_input("Longitude", value="E000°00.00'")
    dme_lat = st.text_input("DME Latitude", value="N00°00.00'")
    dme_lon = st.text_input("DME Longitude", value="E000°00.00'")
    faf_to_mapt_nm = st.number_input("FAF to MAPt Distance (NM)", value=5.0, step=0.1)
    faf_altitude = st.number_input("FAF Altitude (ft)", value=3000)

st.markdown("### Optional Step-Down Fixes (SDFs)")
sdfs = []
for i in range(1, 7):
    col1, col2 = st.columns(2)
    with col1:
        dist = st.number_input(f"SDF {i} Distance (NM)", value=0.0, step=0.1, key=f"sdf_dist_{i}")
    with col2:
        alt = st.number_input(f"SDF {i} Altitude (ft)", value=0, key=f"sdf_alt_{i}")
    if dist > 0 and alt > 0:
        sdfs.append({"Distance": dist, "Altitude": alt, "Fix": f"SDF{i}", "Type": "SDF"})

if st.button("Generate DME & ROD Tables"):
    gp_angle, descent_ft_per_nm, descent_percent = calculate_gp_gradient(faf_altitude, mda, faf_to_mapt_nm)

    st.subheader("Glide Path & Gradient Info")
    st.markdown(f"**GP Angle:** {gp_angle:.2f}°")
    st.markdown(f"**Descent Gradient:** {descent_ft_per_nm} ft/NM ({descent_percent:.2f}%)")

    dme_table = []
    dme_start = dme_at_thr + tod_distance
    dme_end = dme_at_thr
    dme_step = (dme_start - dme_end) / 7

    current_alt = elevation + math.tan(math.radians(gp_angle)) * (dme_start * 6076.12)
    for i in range(8):
        dist = dme_start - i * dme_step
        alt = current_alt - i * descent_ft_per_nm * dme_step
        alt = max(alt, mda)
        dme_table.append({
            "Fix": f"DME{i+1}",
            "Distance": round(dist, 2),
            "Altitude": int(round(alt)),
            "Type": "Generated"
        })

    dme_table[0]["Fix"] = "FAF"
    dme_table[-1]["Fix"] = "MAPT"

    for sdf in sdfs:
        dme_table.append(sdf)
    dme_table = sorted(dme_table, key=lambda x: x["Distance"], reverse=True)

    st.subheader("DME Table")
    dme_df = pd.DataFrame(dme_table)
    st.dataframe(dme_df)

    rod_table = []
    gs_list = [80, 100, 120, 140, 160]
    for gs in gs_list:
        time_min = faf_to_mapt_nm / gs * 60
        rod = (faf_altitude - mda) / time_min if time_min > 0 else 0
        rod_table.append({
            "GS": gs,
            "ROD": int(round(rod, -1)),
            "Time(min)": round(time_min, 2)
        })

    st.subheader("Rate of Descent Table (FAF to MAPT)")
    rod_df = pd.DataFrame(rod_table)
    st.dataframe(rod_df)

    st.subheader("Descent Profile View")
    fig = plot_profile(dme_table, mda)
    st.pyplot(fig)

    st.download_button("Download DME Table CSV", data=dme_df.to_csv(index=False), file_name="dme_table.csv")
    st.download_button("Download ROD Table CSV", data=rod_df.to_csv(index=False), file_name="rod_table.csv")

    pdf_bytes = create_pdf(dme_table, rod_table)
    st.download_button("Download Full PDF Report", data=pdf_bytes, file_name="CDFA_Report.pdf", mime='application/pdf')
