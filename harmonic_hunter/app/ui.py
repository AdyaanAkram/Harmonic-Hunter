from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

import streamlit as st

# -------------------------------------------------
# Ensure project root importable
# -------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# -------------------------------------------------
# Page config + styling
# -------------------------------------------------
st.set_page_config(page_title="Harmonic Hunter", layout="centered")

CUSTOM_CSS = """
<style>
.block-container {padding-top: 2.0rem; padding-bottom: 2.0rem; max-width: 980px;}
h1 {letter-spacing: -0.02em;}
small, .stCaption {opacity: 0.90;}

.stButton > button, .stDownloadButton > button {
  border-radius: 14px !important;
  padding: 0.75rem 1.2rem !important;
  font-weight: 650 !important;
}

.stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
  border-radius: 12px !important;
}

.hh-card {
  border: 1px solid rgba(255,255,255,0.10);
  background: rgba(255,255,255,0.03);
  border-radius: 18px;
  padding: 18px 18px;
}

.hh-muted {opacity: 0.86;}
.hr {height: 1px; background: rgba(255,255,255,0.10); margin: 1.2rem 0;}

.step {
  font-weight: 800;
  font-size: 0.82rem;
  letter-spacing: 0.08em;
  opacity: 0.70;
  margin-bottom: 0.35rem;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# -------------------------------------------------
# Paths
# -------------------------------------------------
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
    "Safe / Baseline": SAMPLES_DIR / "demo_safe.csv",
    "Monitor / Early Warning": SAMPLES_DIR / "demo_monitor.csv",
    "Multiphase Imbalance": SAMPLES_DIR / "demo_multiphase.csv",
    "Critical / High Risk": SAMPLES_DIR / "demo_critical.csv",
}

# -------------------------------------------------
# Header
# -------------------------------------------------
st.title("⚡ Harmonic Hunter")
st.caption("Power-quality risk analysis for facilities and data centers — no hardware required.")

st.markdown(
    """
<div class="hh-card">
  <div style="font-size: 1.05rem; font-weight: 760;">What you get</div>
  <div class="hh-muted" style="margin-top: 6px;">
    • Executive-ready PDF risk report<br/>
    • Phase-level findings + charts<br/>
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
        help="Auto works for most exports.",
    )

    report_kind = st.radio(
        "Report type",
        ["Executive summary", "Full technical"],
        help="Executive is shorter. Full includes more charts + technical details.",
    )

    st.markdown("---")
    st.caption("Tip: Use a baseline to track risk change across weeks/months.")

# -------------------------------------------------
# Step 1
# -------------------------------------------------
st.markdown('<div class="step">STEP 1</div>', unsafe_allow_html=True)
facility = st.text_input("Facility name *", value="", placeholder="Enter facility name (required)")

# -------------------------------------------------
# Step 2 — Demo selection (checkbox single-select)
# -------------------------------------------------
st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
st.markdown('<div class="step">STEP 2</div>', unsafe_allow_html=True)
st.subheader("Choose demo OR upload your own data")

st.session_state.setdefault("demo_selected", None)

c1, c2, c3, c4 = st.columns(4, gap="small")
demo_names = list(DEMOS.keys())

def demo_checkbox(col, name: str):
    checked = (st.session_state.get("demo_selected") == name)
    val = col.checkbox(name, value=checked, key=f"demo_{name}")
    if val and not checked:
        st.session_state["demo_selected"] = name
        st.rerun()
    if (not val) and checked:
        st.session_state["demo_selected"] = None
        st.rerun()

demo_checkbox(c1, demo_names[0])
demo_checkbox(c2, demo_names[1])
demo_checkbox(c3, demo_names[2])
demo_checkbox(c4, demo_names[3])

demo_used = st.session_state.get("demo_selected") is not None

csv_path = None
baseline_csv_path = None

if demo_used:
    csv_path = str(DEMOS[st.session_state["demo_selected"]])
    st.info(f"Using demo dataset: {st.session_state['demo_selected']}")

st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

# Uploads always visible, disabled if demo selected
col_u1, col_u2 = st.columns([1, 1], gap="large")
with col_u1:
    uploaded = st.file_uploader("Upload CSV", type=["csv"], disabled=demo_used)
with col_u2:
    baseline_uploaded = st.file_uploader("Optional baseline CSV", type=["csv"], disabled=demo_used)

if not demo_used:
    if uploaded:
        p = UPLOADS_DIR / uploaded.name
        p.write_bytes(uploaded.getbuffer())
        csv_path = str(p)
    if baseline_uploaded:
        p = UPLOADS_DIR / f"baseline__{baseline_uploaded.name}"
        p.write_bytes(baseline_uploaded.getbuffer())
        baseline_csv_path = str(p)

# -------------------------------------------------
# Step 3 — Generate
# -------------------------------------------------
st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
st.markdown('<div class="step">STEP 3</div>', unsafe_allow_html=True)

generate = st.button("🚀 Generate report", use_container_width=True)

if generate:
    if not facility.strip():
        st.error("Facility name is required.")
        st.stop()

    if not csv_path:
        st.error("Select a demo or upload a CSV.")
        st.stop()

    # Unique output folder per run
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_out_dir = OUTPUTS_DIR / run_id
    run_out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "harmonic_hunter.main",
        csv_path,
        "--map-name", map_name,
        "--facility", facility.strip(),
        "--out-dir", str(run_out_dir),
        "--report-kind", "executive" if report_kind.startswith("Executive") else "full",
    ]

    if baseline_csv_path:
        cmd += ["--baseline-csv", baseline_csv_path]

    # 🔑 Cloud-safe subprocess: run from repo root + set PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT_DIR)

    with st.spinner("Running harmonic risk analysis…"):
        result = subprocess.run(
            cmd,
            cwd=str(ROOT_DIR),
            env=env,
            capture_output=True,
            text=True,
        )

    pdf_path = run_out_dir / "harmonic_hunter_report.pdf"

    if pdf_path.exists():
        input_name = Path(csv_path).name.replace(".csv", "")
        download_name = f"harmonic_report_{input_name}.pdf"

        st.success("Report generated successfully.")
        st.download_button(
            "⬇️ Download PDF Report",
            data=pdf_path.read_bytes(),
            file_name=download_name,
            use_container_width=True,
        )
    else:
        st.error("Report failed to generate. See logs below.")

        with st.expander("Show generation logs"):
            st.write(f"Return code: {result.returncode}")
            st.code(result.stdout or "(no stdout)")
            st.code(result.stderr or "(no stderr)")

st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
st.caption(
    "Advisory analysis based on exported electrical monitoring data. "
    "Not a substitute for on-site inspection or licensed engineering assessment."
)
