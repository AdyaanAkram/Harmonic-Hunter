from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

import streamlit as st

# -------------------------------------------------
# Ensure project root importable (local reliability)
# -------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# -------------------------------------------------
# Page config + premium styling
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

/* -----------------------------
   Demo buttons (checkbox styled)
   - clickable "button"
   - selected highlight
------------------------------ */
div[data-testid="stCheckbox"] label {
  width: 100%;
  justify-content: center;
  border-radius: 14px !important;
  padding: 0.70rem 0.90rem !important;
  border: 1px solid rgba(255,255,255,0.14) !important;
  background: rgba(255,255,255,0.04) !important;
}

div[data-testid="stCheckbox"] label:hover {
  border-color: rgba(255,255,255,0.30) !important;
  background: rgba(255,255,255,0.06) !important;
}

/* hide the square checkbox */
div[data-testid="stCheckbox"] input[type="checkbox"]{
  display: none !important;
}

/* selected state (Safari/Chrome/Edge support :has) */
div[data-testid="stCheckbox"] label:has(input:checked) {
  border-color: rgba(80,160,255,0.80) !important;
  background: rgba(80,160,255,0.20) !important;
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
    "Safe / Baseline": {
        "emoji": "🟢",
        "file": SAMPLES_DIR / "demo_safe.csv",
        "desc": "Stable current with low variability. Establishes a baseline.",
        "baseline": None,
    },
    "Monitor / Early Warning": {
        "emoji": "🟡",
        "file": SAMPLES_DIR / "demo_monitor.csv",
        "desc": "Early indicators of pulsed/non-linear behavior.",
        "baseline": SAMPLES_DIR / "demo_safe.csv",
    },
    "Multiphase Imbalance": {
        "emoji": "🟠",
        "file": SAMPLES_DIR / "demo_multiphase.csv",
        "desc": "Uneven phase behavior; highlights localized phase risk.",
        "baseline": SAMPLES_DIR / "demo_safe.csv",
    },
    "Critical / High Risk": {
        "emoji": "🔴",
        "file": SAMPLES_DIR / "demo_critical.csv",
        "desc": "High variability consistent with elevated risk if sustained.",
        "baseline": SAMPLES_DIR / "demo_safe.csv",
    },
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
# Sidebar (settings)
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
# STEP 1 — Facility
# -------------------------------------------------
st.markdown('<div class="step">STEP 1</div>', unsafe_allow_html=True)
facility = st.text_input(
    "Facility name *",
    value="",
    placeholder="Enter facility name (required)",
)

# -------------------------------------------------
# STEP 2 — Demo selection (single-select toggle buttons)
# -------------------------------------------------
st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
st.markdown('<div class="step">STEP 2</div>', unsafe_allow_html=True)
st.subheader("Choose demo OR upload your own data")
st.caption("Click a demo to select it. Click it again to unselect. Only one can be selected.")

DEMO_NAMES = list(DEMOS.keys())
DEMO_KEYS = {name: f"demo_btn__{i}" for i, name in enumerate(DEMO_NAMES)}

st.session_state.setdefault("demo_selected", None)
# initialize checkbox keys once
for n in DEMO_NAMES:
    st.session_state.setdefault(DEMO_KEYS[n], False)

def _on_demo_toggle(name: str):
    """Enforce single-select + allow unselect by clicking again."""
    key = DEMO_KEYS[name]
    now_checked = bool(st.session_state.get(key, False))
    current = st.session_state.get("demo_selected")

    if now_checked:
        # selecting this demo -> uncheck all others
        st.session_state["demo_selected"] = name
        for other in DEMO_NAMES:
            if other != name:
                st.session_state[DEMO_KEYS[other]] = False
    else:
        # unchecked -> deselect if this was the selected one
        if current == name:
            st.session_state["demo_selected"] = None

# Draw the "button" checkboxes
c1, c2, c3, c4 = st.columns(4, gap="small")

with c1:
    st.checkbox(
        f"{DEMOS[DEMO_NAMES[0]]['emoji']} {DEMO_NAMES[0]}",
        key=DEMO_KEYS[DEMO_NAMES[0]],
        on_change=_on_demo_toggle,
        args=(DEMO_NAMES[0],),
    )
with c2:
    st.checkbox(
        f"{DEMOS[DEMO_NAMES[1]]['emoji']} {DEMO_NAMES[1]}",
        key=DEMO_KEYS[DEMO_NAMES[1]],
        on_change=_on_demo_toggle,
        args=(DEMO_NAMES[1],),
    )
with c3:
    st.checkbox(
        f"{DEMOS[DEMO_NAMES[2]]['emoji']} {DEMO_NAMES[2]}",
        key=DEMO_KEYS[DEMO_NAMES[2]],
        on_change=_on_demo_toggle,
        args=(DEMO_NAMES[2],),
    )
with c4:
    st.checkbox(
        f"{DEMOS[DEMO_NAMES[3]]['emoji']} {DEMO_NAMES[3]}",
        key=DEMO_KEYS[DEMO_NAMES[3]],
        on_change=_on_demo_toggle,
        args=(DEMO_NAMES[3],),
    )

demo_used = st.session_state.get("demo_selected") is not None

csv_path = None
baseline_csv_path = None

if demo_used:
    chosen = st.session_state["demo_selected"]
    demo = DEMOS[chosen]
    csv_path = str(demo["file"])
    baseline_csv_path = str(demo["baseline"]) if demo["baseline"] else None
    st.info(demo["desc"])

st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

# -------------------------------------------------
# Upload section (disabled while demo selected)
# -------------------------------------------------
st.subheader("Upload your own data")

col_u1, col_u2 = st.columns([1, 1], gap="large")

with col_u1:
    uploaded = st.file_uploader(
        "Upload CSV",
        type=["csv"],
        disabled=demo_used,
        help="Disabled while a demo is selected.",
    )

with col_u2:
    baseline_uploaded = st.file_uploader(
        "Optional baseline CSV",
        type=["csv"],
        disabled=demo_used,
        help="Disabled while a demo is selected.",
    )

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
# STEP 3 — Generate
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

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_out_dir = OUTPUTS_DIR / run_id
    run_out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "harmonic_hunter.main",
        csv_path,
        "--map-name",
        map_name,
        "--facility",
        facility.strip(),
        "--out-dir",
        str(run_out_dir),
        "--report-kind",
        "executive" if report_kind.startswith("Executive") else "full",
    ]
    if baseline_csv_path:
        cmd += ["--baseline-csv", baseline_csv_path]

    with st.spinner("Running harmonic risk analysis…"):
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT_DIR),
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
        st.error("Report failed to generate. Check logs below.")
        with st.expander("Debug logs", expanded=True):
            st.code(" ".join(cmd), language="bash")
            st.code(proc.stdout or "", language="text")
            st.code(proc.stderr or "", language="text")

st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
st.caption(
    "Advisory analysis based on exported electrical monitoring data. "
    "Not a substitute for on-site inspection or licensed engineering assessment."
)
