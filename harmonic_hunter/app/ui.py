from __future__ import annotations

import subprocess
from pathlib import Path
import streamlit as st

# -------------------------------------------------
# Page config + premium styling
# -------------------------------------------------
st.set_page_config(page_title="Harmonic Hunter", layout="centered")

CUSTOM_CSS = """
<style>
/* Slightly tighter layout + premium feel */
.block-container {padding-top: 2.0rem; padding-bottom: 2.0rem; max-width: 980px;}
h1 {letter-spacing: -0.02em;}
small, .stCaption {opacity: 0.88;}
/* Button polish */
.stButton > button, .stDownloadButton > button {
  border-radius: 12px !important;
  padding: 0.7rem 1.1rem !important;
  font-weight: 650 !important;
}
/* Inputs */
.stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
  border-radius: 12px !important;
}
/* Card look for sections */
.hh-card {
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.02);
  border-radius: 16px;
  padding: 18px 18px;
}
.hh-muted {opacity: 0.85;}
.hr {height: 1px; background: rgba(255,255,255,0.10); margin: 1.1rem 0;}
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
# Demo datasets (with description + suggested facility name)
# -------------------------------------------------
DEMOS = {
    "🟢 Safe / Baseline": {
        "file": SAMPLES_DIR / "demo_safe.csv",
        "desc": "Stable, low-variability current typical of lightly loaded or linear systems.",
        "facility": "Demo Facility — Safe",
        "baseline": None,
    },
    "🟡 Monitor / Early Warning": {
        "file": SAMPLES_DIR / "demo_monitor.csv",
        "desc": "Early indicators of pulsed or non-linear loading. Monitor trend and expansion impact.",
        "facility": "Demo Facility — Monitor",
        "baseline": SAMPLES_DIR / "demo_safe.csv",
    },
    "🟠 Multiphase Load Imbalance": {
        "file": SAMPLES_DIR / "demo_multiphase.csv",
        "desc": "Uneven phase loading suggesting neutral stress risk and distribution imbalance.",
        "facility": "Demo Facility — Multiphase",
        "baseline": SAMPLES_DIR / "demo_safe.csv",
    },
    "🔴 Critical / High Risk": {
        "file": SAMPLES_DIR / "demo_critical.csv",
        "desc": "High variability consistent with elevated equipment stress risk if sustained.",
        "facility": "Demo Facility — Critical",
        "baseline": SAMPLES_DIR / "demo_safe.csv",
    },
}

# -------------------------------------------------
# Header / value prop
# -------------------------------------------------
st.title("⚡ Harmonic Hunter")
st.caption(
    "Power-quality risk analysis for facilities and data centers. "
    "Upload existing **PDU / UPS** exports — **no hardware required**."
)

st.markdown(
    """
<div class="hh-card">
  <div style="font-size: 1.05rem; font-weight: 700;">What you get</div>
  <div class="hh-muted" style="margin-top: 6px;">
    • A clean PDF risk report<br/>
    • Phase-level findings + explainable recommendations<br/>
    • Optional baseline comparison (“what changed?”)
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

# -------------------------------------------------
# Sidebar (more “product-like”)
# -------------------------------------------------
with st.sidebar:
    st.subheader("⚙️ Report settings")
    map_name = st.selectbox(
        "CSV format",
        ["auto", "default", "apc_like", "vertiv_like", "eaton_like"],
        help="Auto works for most exports.",
    )

    report_kind = st.radio(
        "Report type",
        ["Executive summary", "Full technical"],
        help="Executive is shorter. Full includes charts + technical findings.",
    )

    st.markdown("---")
    st.caption("Tip: Use a baseline for trend tracking across weeks/months.")

# -------------------------------------------------
# Facility (required, default blank)
# -------------------------------------------------
facility = st.text_input(
    "Facility name *",
    value="",
    placeholder="Enter facility name (required)",
)

# -------------------------------------------------
# Demo section
# -------------------------------------------------
st.subheader("🧪 Try a demo report")
st.write("Explore behavior under different electrical conditions using pre-generated samples.")

demo_choice = st.radio("Select a demo scenario", list(DEMOS.keys()), index=None)

demo_csv_path = None
demo_baseline_path = None

if demo_choice:
    demo_csv_path = str(DEMOS[demo_choice]["file"])
    demo_baseline_path = DEMOS[demo_choice]["baseline"]
    st.info(DEMOS[demo_choice]["desc"])

    # Auto-fill facility name if user hasn’t typed anything
    if not facility.strip():
        facility = DEMOS[demo_choice]["facility"]
        st.session_state["facility_autofill"] = facility

# Keep text input in sync with demo autofill
if "facility_autofill" in st.session_state and not st.session_state.get("facility_user_edited", False):
    # Streamlit can’t directly overwrite the widget reliably unless you bind a key.
    pass

# Bind facility input to a key to allow overwrite
st.session_state.setdefault("facility_value", facility)
facility = st.text_input(
    "Facility name (override demo if needed) *",
    key="facility_value",
    placeholder="Enter facility name (required)",
)

st.session_state["facility_user_edited"] = True if facility.strip() else st.session_state.get("facility_user_edited", False)

st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

# -------------------------------------------------
# Upload section (disabled if demo selected)
# -------------------------------------------------
st.subheader("📤 Upload your own data")

col_u1, col_u2 = st.columns([1, 1], gap="large")

with col_u1:
    uploaded = st.file_uploader(
        "Upload a PDU / UPS CSV export",
        type=["csv"],
        disabled=bool(demo_choice),
        help="Disable demo to upload.",
    )

with col_u2:
    baseline_uploaded = st.file_uploader(
        "Optional baseline CSV (for “what changed?”)",
        type=["csv"],
        disabled=bool(demo_choice),
        help="Upload a previous export to compare against current.",
    )

# -------------------------------------------------
# Resolve paths
# -------------------------------------------------
csv_path = None
baseline_csv_path = None

if demo_choice:
    csv_path = demo_csv_path
    baseline_csv_path = str(demo_baseline_path) if demo_baseline_path else None
else:
    if uploaded:
        save_path = UPLOADS_DIR / uploaded.name
        with open(save_path, "wb") as f:
            f.write(uploaded.getbuffer())
        csv_path = str(save_path)

    if baseline_uploaded:
        save_base_path = UPLOADS_DIR / f"baseline__{baseline_uploaded.name}"
        with open(save_base_path, "wb") as f:
            f.write(baseline_uploaded.getbuffer())
        baseline_csv_path = str(save_base_path)

# -------------------------------------------------
# Generate
# -------------------------------------------------
st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

cta_col1, cta_col2 = st.columns([1, 1], gap="large")
with cta_col1:
    generate = st.button("🚀 Generate report", use_container_width=True)

with cta_col2:
    st.caption(
        "After generation, download the PDF. "
        "For production, deploy to Streamlit Cloud and share the link."
    )

if generate:
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
        facility.strip(),
        "--out-dir",
        str(OUTPUTS_DIR),
        "--report-kind",
        "executive" if report_kind.startswith("Executive") else "full",
    ]

    if baseline_csv_path:
        cmd += ["--baseline-csv", baseline_csv_path]

    with st.spinner("Running harmonic risk analysis…"):
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

        # “What to look for” guidance (Phase 1 polish)
        st.markdown(
            """
<div class="hh-card">
  <div style="font-size: 1.02rem; font-weight: 700;">What to look for in this report</div>
  <div class="hh-muted" style="margin-top: 6px;">
    • Risk band + score (top of page 1)<br/>
    • “Key observations” (what’s driving risk)<br/>
    • Recommendations (actionable next steps)<br/>
    • If baseline is present: “Change since baseline”
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
    else:
        st.error("Report failed to generate. Check terminal output/logs.")

st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

# -------------------------------------------------
# Footer / disclaimer
# -------------------------------------------------
st.caption(
    "Harmonic Hunter provides advisory analysis based on exported electrical monitoring data. "
    "It does not replace on-site inspection or licensed engineering assessment."
)
