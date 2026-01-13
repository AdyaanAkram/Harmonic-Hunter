from __future__ import annotations

import subprocess
from pathlib import Path
from datetime import datetime
import streamlit as st
import sys

# -------------------------------------------------
# Page config + premium styling
# -------------------------------------------------
st.set_page_config(page_title="Harmonic Hunter", layout="centered")

CUSTOM_CSS = """
<style>
.block-container {padding-top: 2rem; padding-bottom: 2rem; max-width: 980px;}
h1 {letter-spacing: -0.02em;}
.stButton > button, .stDownloadButton > button {
  border-radius: 12px; padding: 0.7rem 1.1rem; font-weight: 650;
}
.stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
  border-radius: 12px;
}
.hh-card {
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.02);
  border-radius: 16px;
  padding: 18px;
}
.hr {height:1px;background:rgba(255,255,255,0.1);margin:1.1rem 0;}
.hh-muted {opacity:0.85;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# -------------------------------------------------
# Paths
# -------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
SAMPLES_DIR = DATA_DIR / "samples"
UPLOADS_DIR = DATA_DIR / "uploads"
OUTPUTS_DIR = DATA_DIR / "outputs"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------
# Demo datasets
# -------------------------------------------------
DEMOS = {
    "🟢 Safe / Baseline": {
        "file": SAMPLES_DIR / "demo_safe.csv",
        "desc": "Stable, low-variability current typical of linear loads.",
        "facility": "Demo Facility — Safe",
        "baseline": None,
    },
    "🟡 Monitor / Early Warning": {
        "file": SAMPLES_DIR / "demo_monitor.csv",
        "desc": "Early indicators of pulsed or non-linear loading.",
        "facility": "Demo Facility — Monitor",
        "baseline": SAMPLES_DIR / "demo_safe.csv",
    },
    "🟠 Multiphase Load Imbalance": {
        "file": SAMPLES_DIR / "demo_multiphase.csv",
        "desc": "Uneven phase loading with imbalance risk.",
        "facility": "Demo Facility — Multiphase",
        "baseline": SAMPLES_DIR / "demo_safe.csv",
    },
    "🔴 Critical / High Risk": {
        "file": SAMPLES_DIR / "demo_critical.csv",
        "desc": "High variability consistent with elevated equipment stress.",
        "facility": "Demo Facility — Critical",
        "baseline": SAMPLES_DIR / "demo_safe.csv",
    },
}

# -------------------------------------------------
# Header
# -------------------------------------------------
st.title("⚡ Harmonic Hunter")
st.caption(
    "Power-quality risk analysis for facilities and data centers. "
    "Upload existing **PDU / UPS** exports — **no hardware required**."
)

st.markdown(
    """
<div class="hh-card">
<b>What you get</b><br/>
<div class="hh-muted">
• Executive-ready PDF report<br/>
• Phase-level findings & charts<br/>
• Explainable recommendations<br/>
• Optional baseline comparison (“what changed?”)
</div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

# -------------------------------------------------
# Sidebar
# -------------------------------------------------
with st.sidebar:
    st.subheader("⚙️ Report settings")
    map_name = st.selectbox(
        "CSV format",
        ["auto", "default", "apc_like", "vertiv_like", "eaton_like"],
    )
    report_kind = st.radio(
        "Report type",
        ["Executive summary", "Full technical"],
    )

# -------------------------------------------------
# Demo selection
# -------------------------------------------------
st.subheader("🧪 Try a demo report")
demo_choice = st.radio("Select a demo scenario", list(DEMOS.keys()), index=None)

demo_csv = None
demo_baseline = None
demo_facility = ""

if demo_choice:
    demo = DEMOS[demo_choice]
    demo_csv = str(demo["file"])
    demo_baseline = str(demo["baseline"]) if demo["baseline"] else None
    demo_facility = demo["facility"]
    st.info(demo["desc"])

# -------------------------------------------------
# Facility (SINGLE input – fixed)
# -------------------------------------------------
facility = st.text_input(
    "Facility name *",
    value=demo_facility,
    placeholder="Enter facility name (required)",
)

st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

# -------------------------------------------------
# Uploads (disabled during demo)
# -------------------------------------------------
st.subheader("📤 Upload your own data")

uploaded = st.file_uploader(
    "Upload a PDU / UPS CSV export",
    type=["csv"],
    disabled=bool(demo_choice),
)

baseline_uploaded = st.file_uploader(
    "Optional baseline CSV",
    type=["csv"],
    disabled=bool(demo_choice),
)

# -------------------------------------------------
# Resolve paths
# -------------------------------------------------
csv_path = None
baseline_path = None

if demo_choice:
    csv_path = demo_csv
    baseline_path = demo_baseline
else:
    if uploaded:
        p = UPLOADS_DIR / uploaded.name
        p.write_bytes(uploaded.getbuffer())
        csv_path = str(p)

    if baseline_uploaded:
        p = UPLOADS_DIR / f"baseline__{baseline_uploaded.name}"
        p.write_bytes(baseline_uploaded.getbuffer())
        baseline_path = str(p)

# -------------------------------------------------
# Generate
# -------------------------------------------------
st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

if st.button("🚀 Generate report", use_container_width=True):
    if not facility.strip():
        st.error("Facility name is required.")
        st.stop()
    if not csv_path:
        st.error("Select a demo or upload a CSV.")
        st.stop()

    # 🔑 Unique run folder (fixes identical demo outputs)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_out = OUTPUTS_DIR / run_id
    run_out.mkdir(parents=True, exist_ok=True)

    cmd = [
    sys.executable,  # 🔑 critical fix
    str(ROOT_DIR / "harmonic_hunter" / "main.py"),
    csv_path,
    "--map-name", map_name,
    "--facility", facility,
    "--out-dir", str(run_out),
    "--report-kind", "executive" if report_kind.startswith("Executive") else "full",
]

    if baseline_path:
        cmd += ["--baseline-csv", baseline_path]

    with st.spinner("Running harmonic risk analysis…"):
        subprocess.run(cmd, check=False)

    pdf = run_out / "harmonic_hunter_report.pdf"
    if pdf.exists():
        st.success("Report generated successfully.")
        st.download_button(
            "⬇️ Download PDF",
            data=pdf.read_bytes(),
            file_name="harmonic_hunter_report.pdf",
            use_container_width=True,
        )
    else:
        st.error("Report failed to generate.")

st.caption(
    "Advisory analysis based on exported monitoring data. "
    "Not a substitute for licensed engineering assessment."
)
