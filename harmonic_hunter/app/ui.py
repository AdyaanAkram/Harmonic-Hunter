from __future__ import annotations

import subprocess
from pathlib import Path
import streamlit as st

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(
    page_title="Harmonic Hunter",
    layout="centered",
)

# -------------------------------------------------
# Paths
# -------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
SAMPLES_DIR = DATA_DIR / "samples"
UPLOADS_DIR = DATA_DIR / "uploads"
OUTPUTS_DIR = DATA_DIR / "outputs"

UPLOADS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)

# -------------------------------------------------
# Demo datasets
# -------------------------------------------------
DEMOS = {
    "🟢 Safe / Baseline": SAMPLES_DIR / "demo_safe.csv",
    "🟡 Monitor / Early Warning": SAMPLES_DIR / "demo_monitor.csv",
    "🟠 Multiphase Load Imbalance": SAMPLES_DIR / "demo_multiphase.csv",
    "🔴 Critical / High Risk": SAMPLES_DIR / "demo_critical.csv",
}

# -------------------------------------------------
# Header
# -------------------------------------------------
st.title("⚡ Harmonic Hunter")
st.caption(
    "Power-quality risk analysis for data centers and facilities. "
    "Upload existing PDU / UPS exports — **no hardware required**."
)

st.divider()

# -------------------------------------------------
# Required facility name
# -------------------------------------------------
facility = st.text_input(
    "Facility name *",
    placeholder="Enter facility name",
)

map_name = st.selectbox(
    "CSV format",
    ["auto", "default", "apc_like", "vertiv_like", "eaton_like"],
)

# -------------------------------------------------
# Demo selection
# -------------------------------------------------
st.subheader("🧪 Try a demo report")

demo_choice = st.radio(
    "Select a demo scenario",
    list(DEMOS.keys()),
    index=None,
)

st.divider()

# -------------------------------------------------
# Upload
# -------------------------------------------------
st.subheader("📤 Upload your own data")

uploaded = st.file_uploader(
    "Upload a PDU / UPS CSV export",
    type=["csv"],
)

# -------------------------------------------------
# Resolve CSV path
# -------------------------------------------------
csv_path = None

if demo_choice:
    csv_path = str(DEMOS[demo_choice])
elif uploaded:
    save_path = UPLOADS_DIR / uploaded.name
    with open(save_path, "wb") as f:
        f.write(uploaded.getbuffer())
    csv_path = str(save_path)

# -------------------------------------------------
# Generate
# -------------------------------------------------
st.divider()

if st.button("🚀 Generate Harmonic Risk Report", use_container_width=True):
    if not facility.strip():
        st.error("Facility name is required.")
        st.stop()

    if not csv_path:
        st.error("Select a demo or upload a CSV.")
        st.stop()

    cmd = [
        "python",
        "-m",
        "harmonic_hunter.main",
        csv_path,
        "--map-name",
        map_name,
        "--facility",
        facility,
        "--out-dir",
        str(OUTPUTS_DIR),
    ]

    with st.spinner("Running analysis…"):
        subprocess.run(cmd, check=False)

    pdf_path = OUTPUTS_DIR / "harmonic_hunter_report.pdf"

    if pdf_path.exists():
        st.success("Report generated successfully.")
        with open(pdf_path, "rb") as f:
            st.download_button(
                "⬇️ Download PDF Report",
                f,
                file_name="harmonic_hunter_report.pdf",
                use_container_width=True,
            )
    else:
        st.error("Report failed to generate.")
