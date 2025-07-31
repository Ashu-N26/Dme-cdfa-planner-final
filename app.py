import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from fpdf import FPDF
import io

st.set_page_config(page_title="DME/CDFA Descent Planner", layout="wide")
st.title("🧮 DME/CDFA Descent Planner Tool")

# Sidebar Inputs
st.sidebar.header("✈️ Descent Input Parameters")
elevation = st.sidebar.number_input("Threshold Elevation (ft)", value=150)
mda = st.sidebar.number_input("MDA (ft)", value=450)
tod = st.sidebar.number_input("Top of Descent Altitude (ft)", value=2000)
dme_thr = st.sidebar.number_input("DME Distance at THR", value=0.5, format="%.1f")
dme_faf = st.sidebar.number_input("FAF DME Distance", value=6.0, format="%.1f")
dme_mapt = st.sidebar.number_input("MAPt DME Distance", value=1.2, format="%.1f")

st.sidebar.markdown("### ➕ Step-Down Fixes (SDFs)")
sdf_count = st.sidebar.slider("Number of SDFs", 0, 3, 1)
sdfs = []
for i in range(sdf_count):
    dist = st.sidebar.number_input(f"SDF {i+1} - Distance", value=2.5 + i, step=0.1, format="%.1f", key=f"sd{i}")
    alt = st.sidebar.number_input(f"SDF {i+1} - Altitude (ft)", value=800 + 100*i, step=10, key=f"sa{i}")
    sdfs.append({"Distance": dist, "Altitude": alt, "Label": f"SDF{i+1}"})

# Compute Descent Profile
points = [{"Distance": dme_faf, "Altitude": tod, "Label": "FAF"}]
points.extend(sdfs)
points.append({"Distance": dme_mapt, "Altitude": mda, "Label": "MAPt"})

# Sort descending by DME
points = sorted(points, key=lambda x: -x["Distance"])
# Fill to max 8 rows by interpolating
while len(points) < 8:
    last = points[-1]
    delta_dme = (last["Distance"] - dme_thr) / (8 - len(points))
    new_dist = last["Distance"] - delta_dme
    new_alt = last["Altitude"] - ((last["Altitude"] - elevation) / (8 - len(points)))
    points.append({"Distance": round(new_dist, 2), "Altitude": round(new_alt, 0), "Label": ""})
# Add threshold entry if not included
if all(abs(p["Distance"] - dme_thr) > 0.1 for p in points):
    points.append({"Distance": dme_thr, "Altitude": elevation, "Label": "THR"})
# Sort again
points = sorted(points, key=lambda x: -x["Distance"])

# DME Table
dme_df = pd.DataFrame(points)
dme_df = dme_df.head(8)
st.subheader("📋 DME Altitude Table")
st.dataframe(dme_df)

# ROD Table
st.subheader("📉 Rate of Descent (ROD) Table")
groundspeeds = [80, 100, 120, 140, 160]
rod_rows = []
dist_nm = dme_faf - dme_mapt
for gs in groundspeeds:
    time_min = dist_nm / gs * 60
    alt_diff = tod - mda
    rod = (alt_diff / time_min) * 60 if time_min > 0 else 0
    rod_rows.append({
        "GS (kt)": gs,
        "Time (min)": f"{time_min:.2f}",
        "ROD (ft/min)": int(round(rod / 10.0) * 10)
    })
rod_df = pd.DataFrame(rod_rows)
st.dataframe(rod_df)

# Chart
st.subheader("📈 Visual Descent Profile")
fig, ax = plt.subplots()
ax.plot([p["Distance"] for p in dme_df], [p["Altitude"] for p in dme_df], marker='o')
for p in dme_df.itertuples():
    label = p.Label if p.Label else ""
    ax.annotate(label, (p.Distance, p.Altitude), textcoords="offset points", xytext=(0,5), ha='center')
ax.axhline(mda, color='red', linestyle='--', label="MDA")
ax.set_xlabel("DME Distance (NM)")
ax.set_ylabel("Altitude (ft)")
ax.invert_xaxis()
ax.legend()
st.pyplot(fig)

# Export: PDF
pdf = FPDF()
pdf.add_page()
pdf.set_font("Arial", "B", 14)
pdf.cell(0, 10, "DME/CDFA Descent Planner", ln=True)
pdf.set_font("Arial", "", 12)

pdf.cell(0, 10, "DME Table", ln=True)
for row in dme_df.itertuples():
    pdf.cell(0, 8, f"{row.Label or '-'}  |  {row.Distance} NM  |  {int(row.Altitude)} ft", ln=True)

pdf.ln(5)
pdf.cell(0, 10, "ROD Table", ln=True)
for row in rod_df.itertuples():
    pdf.cell(0, 8, f"{row._1} kt  |  {row._2} min  |  {row._3} ft/min", ln=True)

pdf_output = pdf.output(dest="S").encode("latin1")
st.download_button("📄 Download PDF", pdf_output, "DME_CDFA_Report.pdf", mime="application/pdf")

# Export: CSVs
dme_csv = dme_df.to_csv(index=False).encode("utf-8")
rod_csv = rod_df.to_csv(index=False).encode("utf-8")

st.download_button("📥 Download DME Table CSV", dme_csv, "DME_Table.csv", mime="text/csv")
st.download_button("📥 Download ROD Table CSV", rod_csv, "ROD_Table.csv", mime="text/csv")
