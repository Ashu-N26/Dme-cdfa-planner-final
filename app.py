import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from fpdf import FPDF
import math
import io

st.set_page_config(page_title="DME/CDFA Descent Planner", layout="wide")
st.title("🧮 DME/CDFA Descent Planner Tool")

# Sidebar Inputs
st.sidebar.header("✈️ Descent Planning Inputs")
elevation = st.sidebar.number_input("Threshold Elevation (ft)", value=150)
mda = st.sidebar.number_input("Minimum Descent Altitude (MDA) (ft)", value=450)
tod_alt = st.sidebar.number_input("Top of Descent Altitude (ft)", value=2000)
dme_thr = st.sidebar.number_input("DME at Threshold (NM)", value=0.5)
dme_faf = st.sidebar.number_input("DME at FAF (NM)", value=6.0)
dme_mapt = st.sidebar.number_input("DME at MAPt (NM)", value=1.2)
faf_mapt_distance = st.sidebar.number_input("Distance FAF to MAPt (NM)", value=4.8, format="%.2f")

# Step-Down Fixes (up to 6)
sdf_count = st.sidebar.slider("Number of SDFs", 0, 6, 2)
sdfs = []
for i in range(sdf_count):
    dist = st.sidebar.number_input(f"SDF {i+1} - Distance (NM)", value=3.5 - i, step=0.1, format="%.1f", key=f"sdf_d{i}")
    alt = st.sidebar.number_input(f"SDF {i+1} - Altitude (ft)", value=900 - 100*i, step=10, key=f"sdf_a{i}")
    sdfs.append({"Distance": dist, "Altitude": alt, "Label": f"SDF{i+1}"})

# GP angle and descent gradient (slant-range corrected)
horizontal_ft = (dme_faf - dme_thr) * 6076.12  # NM to ft
vertical_ft = tod_alt - elevation
slant_distance = math.sqrt(horizontal_ft**2 + vertical_ft**2)
gp_angle_deg = math.degrees(math.atan(vertical_ft / horizontal_ft)) if horizontal_ft else 0
descent_gradient = (vertical_ft / horizontal_ft) * 100 if horizontal_ft else 0

st.markdown(f"### 📐 GP Angle: `{gp_angle_deg:.2f}°`  📉 Descent Gradient: `{descent_gradient:.2f}%`")

# Build DME Altitude Table (1 NM steps from FAF to THR)
fixes = [{"Distance": dme_faf, "Altitude": tod_alt, "Label": "FAF"}]
fixes.extend(sdfs)
fixes.append({"Distance": dme_mapt, "Altitude": mda, "Label": "MAPt"})
fixes.append({"Distance": dme_thr, "Altitude": elevation, "Label": "THR"})

# Remove duplicates by Distance
unique_fixes = {round(f["Distance"], 2): f for f in fixes}
fixes = list(unique_fixes.values())
fixes.sort(key=lambda x: -x["Distance"])

# Interpolate to 1 NM steps (max 8 rows, stop at MDA)
dme_table = []
start = dme_faf
end = max(dme_thr, dme_mapt)
steps = int(abs(start - end)) + 1
dme_points = np.linspace(start, end, num=steps)

for dme in dme_points:
    if dme > dme_faf or dme < dme_thr:
        continue
    matching_fix = next((f for f in fixes if abs(f["Distance"] - dme) < 0.01), None)
    if matching_fix:
        alt = matching_fix["Altitude"]
        label = matching_fix["Label"]
    else:
        # Linear interpolation
        above = next((f for f in fixes if f["Distance"] >= dme), None)
        below = next((f for f in reversed(fixes) if f["Distance"] <= dme), None)
        if above and below and above != below:
            ratio = (dme - below["Distance"]) / (above["Distance"] - below["Distance"])
            alt = below["Altitude"] + ratio * (above["Altitude"] - below["Altitude"])
        else:
            alt = elevation
        label = ""
    alt = max(alt, mda) if dme <= dme_mapt else alt
    dme_table.append({"Distance (NM)": round(dme, 2), "Altitude (ft)": int(round(alt)), "Fix": label})

# Trim to max 8 rows
dme_table = dme_table[:8]
dme_df = pd.DataFrame(dme_table)
st.subheader("📋 DME Table")
st.dataframe(dme_df)
# Build ROD Table
st.subheader("📉 ROD Table (FAF to MAPt)")
gs_list = [80, 100, 120, 140, 160]  # in knots
distance_ft = faf_mapt_distance * 6076.12
altitude_drop = tod_alt - mda
time_minutes = distance_ft / (np.array(gs_list) * 6076.12 / 60)  # convert knots to ft/min then to minutes
rod_values = np.round(altitude_drop / time_minutes / 10) * 10  # round to nearest 10

rod_df = pd.DataFrame({
    "GS (kt)": gs_list,
    "ROD (ft/min)": rod_values.astype(int),
    "Time FAF→MAPt (min)": time_minutes.round(2)
})
st.dataframe(rod_df)

# Chart
# Updated Visual Descent Profile with MDA line and plotted fix labels
st.subheader("📈 Visual Descent Profile")
fig, ax = plt.subplots(figsize=(10, 4))

# Plot the descent path with markers
ax.plot(dme_df["Distance (NM)"], dme_df["Altitude (ft)"], marker='o', linestyle='-', color='blue', label="Descent Path")

# Plot fix points with labels
for point in dme_df.itertuples():
    if point.Fix:
        ax.plot(point._1, point._2, 'ro')  # Red marker at fix
        ax.annotate(point.Fix, (point._1, point._2), textcoords="offset points", xytext=(0, 5), ha='center', fontsize=9)

# Add red horizontal line for MDA
ax.axhline(y=mda, color='red', linestyle='--', linewidth=1.5, label="MDA")

# Axes labels and legend
ax.set_xlabel("DME Distance (NM)")
ax.set_ylabel("Altitude (ft)")
ax.grid(True)
ax.legend()

st.pyplot(fig)

# Export to PDF
def create_pdf(dme_df, rod_df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "DME/CDFA Descent Planning Report", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"GP Angle: {gp_angle_deg:.2f}°, Gradient: {descent_gradient:.2f}%", ln=True)

    # DME Table
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "DME Table:", ln=True)
    pdf.set_font("Arial", "", 11)
    for row in dme_df.itertuples(index=False):
        fix_label = row[2] if row[2] else ""
        pdf.cell(0, 8, f"DME: {row[0]} NM    Alt: {row[1]} ft    Fix: {fix_label}", ln=True)

    # ROD Table
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "ROD Table:", ln=True)
    pdf.set_font("Arial", "", 11)
    for row in rod_df.itertuples(index=False):
        pdf.cell(0, 8, f"GS: {row[0]} kt    ROD: {row[1]} ft/min    Time: {row[2]} min", ln=True)

    return pdf.output(dest='S').encode('latin1', 'ignore')

pdf_bytes = create_pdf(dme_df, rod_df)
st.download_button("📄 Download PDF", pdf_bytes, file_name="dme_cdfa_report.pdf")

# Export CSVs
csv_dme = dme_df.to_csv(index=False).encode("utf-8")
csv_rod = rod_df.to_csv(index=False).encode("utf-8")
col1, col2 = st.columns(2)
with col1:
    st.download_button("⬇️ Download DME Table CSV", csv_dme, "dme_table.csv")
with col2:
    st.download_button("⬇️ Download ROD Table CSV", csv_rod, "rod_table.csv")
