import streamlit as st
import pandas as pd
import math
import matplotlib.pyplot as plt
from fpdf import FPDF
from io import BytesIO

st.set_page_config(layout="centered", page_title="DME/CDFA Descent Planner Tool")

def calculate_gp_angle(start_altitude, end_altitude, distance_nm):
    height_diff_ft = start_altitude - end_altitude
    angle_rad = math.atan(height_diff_ft / (distance_nm * 6076.12))
    angle_deg = round(math.degrees(angle_rad), 1)
    gradient = round((height_diff_ft / (distance_nm * 6076.12)) * 100, 1)
    return angle_deg, gradient

def generate_dme_table(start_altitude, end_altitude, total_distance, mda, sdf_list):
    step = total_distance / 7
    dme_points = [round(total_distance - i * step, 2) for i in range(8)]
    dme_points[-1] = round(dme_points[-2] - step, 2)

    altitude_diff = start_altitude - end_altitude
    altitudes = [round(start_altitude - (i * (altitude_diff / 7))) for i in range(8)]

    data = []
    for i in range(8):
        alt = max(altitudes[i], mda)
        label = ""
        for sdf in sdf_list:
            if sdf and abs(dme_points[i] - float(sdf[0])) < 0.05:
                alt = float(sdf[1])
                label = "SDF"
        if i == 0:
            label = "FAF"
        elif i == 7:
            label = "MAPt"
        data.append({"Distance": dme_points[i], "Altitude": alt, "Label": label})
    return data

def generate_rod_table(altitude_diff, faf_to_mapt_distance):
    rod_table = []
    for gs in [100, 120, 140, 160]:
        time_min = (faf_to_mapt_distance / gs) * 60
        rod = (altitude_diff / time_min) * 60
        rod_table.append({"GS (kt)": gs, "ROD (ft/min)": round(rod)})
    return rod_table

def plot_descent_profile(dme_data, mda):
    fig, ax = plt.subplots()
    distances = [d["Distance"] for d in dme_data]
    altitudes = [d["Altitude"] for d in dme_data]
    ax.plot(distances, altitudes, marker='o', color='blue')

    for i, d in enumerate(dme_data):
        ax.text(d["Distance"], d["Altitude"] + 100, d["Label"], fontsize=8)

    ax.axhline(y=mda, color='red', linestyle='--', label='MDA')
    ax.set_xlabel("DME (NM)")
    ax.set_ylabel("Altitude (ft)")
    ax.set_title("CDFA Profile View")
    ax.invert_xaxis()
    ax.invert_yaxis()
    ax.legend()
    return fig

def create_pdf(dme_table, rod_table):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "DME/CDFA Descent Planner Report", ln=True, align="C")

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, "DME Table", ln=True)

    pdf.set_font("Arial", '', 11)
    for row in dme_table:
        label = row["Label"] if row["Label"] else "-"
        pdf.cell(200, 8, f"{row['Distance']} NM | {row['Altitude']} ft | {label}", ln=True)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, "ROD Table (from FAF to MAPt)", ln=True)

    pdf.set_font("Arial", '', 11)
    for row in rod_table:
        pdf.cell(200, 8, f"{row['GS (kt)']} kt | ROD: {row['ROD (ft/min)']} ft/min", ln=True)

    # Save to buffer
    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer

st.title("DME/CDFA Descent Planner Tool")

with st.form("planner_form"):
    st.subheader("Enter Descent Parameters:")
    airport_elev = st.number_input("Airport Elevation (ft)", value=200)
    faf_altitude = st.number_input("FAF Altitude (ft)", value=3000)
    mda = st.number_input("Minimum Descent Altitude (MDA ft)", value=800)
    faf_distance = st.number_input("FAF Distance (NM)", value=5.2)
    faf_to_mapt_distance = st.number_input("FAF to MAPt Distance (NM)", value=5.2)

    sdf_list = []
    st.markdown("### Optional: Step-Down Fixes (SDFs)")
    for i in range(1, 7):
        col1, col2 = st.columns(2)
        with col1:
            dist = st.text_input(f"SDF {i} Distance (NM)", key=f"sdf_dist_{i}")
        with col2:
            alt = st.text_input(f"SDF {i} Altitude (ft)", key=f"sdf_alt_{i}")
        if dist and alt:
            try:
                sdf_list.append((float(dist), float(alt)))
            except:
                st.warning(f"Invalid SDF {i} entry ignored.")

    submitted = st.form_submit_button("Generate Tables")

if submitted:
    gp_angle, gradient = calculate_gp_angle(faf_altitude, mda, faf_distance)
    st.markdown(f"**Glide Path Angle**: {gp_angle}° | **Descent Gradient**: {gradient}%")

    dme_table = generate_dme_table(faf_altitude, mda, faf_distance, mda, sdf_list)
    rod_table = generate_rod_table(faf_altitude - mda, faf_to_mapt_distance)

    dme_df = pd.DataFrame(dme_table)
    rod_df = pd.DataFrame(rod_table)

    st.subheader("DME Table")
    st.dataframe(dme_df)

    st.subheader("Rate of Descent (ROD) Table")
    st.dataframe(rod_df)

    fig = plot_descent_profile(dme_table, mda)
    st.pyplot(fig)

    pdf_buffer = create_pdf(dme_table, rod_table)
    st.download_button("Download PDF Report", data=pdf_buffer, file_name="CDFA_Descent_Plan.pdf")

    st.download_button("Download DME CSV", data=dme_df.to_csv(index=False), file_name="DME_Table.csv")
    st.download_button("Download ROD CSV", data=rod_df.to_csv(index=False), file_name="ROD_Table.csv")

