# =============================
# DROP-IN DEBUGGING UPGRADE
# Paste this whole block into your file:
# 1) Add the imports (os, traceback)
# 2) Add the helper functions
# 3) Replace your existing `if generate:` block with the new one below
# =============================

from __future__ import annotations

import sys
import os
import subprocess
import traceback
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
# Debug helpers
# -------------------------------------------------
def _exists(p: str | Path | None) -> bool:
    if not p:
        return False
    return Path(p).exists()

def _head_tail(text: str, head: int = 2000, tail: int = 4000) -> str:
    """Keep logs readable; show start+end if huge."""
    if not text:
        return ""
    if len(text) <= head + tail + 50:
        return text
    return text[:head] + "\n\n... (snip) ...\n\n" + text[-tail:]

def run_cmd_with_logs(cmd: list[str], cwd: Path | None = None, timeout: int = 600):
    """
    Run subprocess, capture stdout/stderr, return CompletedProcess.
    Also prints to server logs for Streamlit Cloud debugging.
    """
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
        # Print to cloud logs
        print("\n[HARMONIC_HUNTER] CMD:", " ".join(cmd))
        print("[HARMONIC_HUNTER] RETURN CODE:", proc.returncode)
        if proc.stdout:
            print("[HARMONIC_HUNTER] STDOUT:\n", proc.stdout)
        if proc.stderr:
            print("[HARMONIC_HUNTER] STDERR:\n", proc.stderr)
        return proc
    except subprocess.TimeoutExpired as e:
        print("[HARMONIC_HUNTER] TIMEOUT:", str(e))
        raise
    except Exception as e:
        print("[HARMONIC_HUNTER] EXCEPTION:", repr(e))
        raise

def debug_panel(run_out_dir: Path, cmd: list[str], proc: subprocess.CompletedProcess | None, extra: dict):
    """Show a nice debug panel in the UI."""
    with st.expander("🧪 Debug details (click to expand)", expanded=True):
        st.markdown("**Environment**")
        st.code(
            "\n".join(
                [
                    f"python: {sys.version}",
                    f"executable: {sys.executable}",
                    f"cwd: {os.getcwd()}",
                    f"ROOT_DIR: {ROOT_DIR}",
                    f"run_out_dir: {run_out_dir}",
                ]
            ),
            language="text",
        )

        st.markdown("**Command**")
        st.code(" ".join(cmd), language="bash")

        st.markdown("**Paths / existence**")
        st.json(extra)

        if proc is not None:
            st.markdown("**Return code**")
            st.code(str(proc.returncode), language="text")

            st.markdown("**STDOUT**")
            st.code(_head_tail(proc.stdout or ""), language="text")

            st.markdown("**STDERR**")
            st.code(_head_tail(proc.stderr or ""), language="text")

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
# STEP 1 — Facility (single input)
# -------------------------------------------------
st.markdown('<div class="step">STEP 1</div>', unsafe_allow_html=True)
facility = st.text_input(
    "Facility name *",
    value="",
    placeholder="Enter facility name (required)",
)

# -------------------------------------------------
# STEP 2 — Demo selection (single-select)
# -------------------------------------------------
st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
st.markdown('<div class="step">STEP 2</div>', unsafe_allow_html=True)
st.subheader("Choose demo OR upload your own data")

st.caption("Select a demo to run it. Click the same demo again to deselect.")

st.session_state.setdefault("demo_selected", None)

c1, c2, c3, c4 = st.columns(4, gap="small")
demo_names = list(DEMOS.keys())

def _demo_checkbox(col, name: str):
    checked = (st.session_state.get("demo_selected") == name)
    val = col.checkbox(f"{DEMOS[name]['emoji']} {name}", value=checked, key=f"demo_{name}")
    if val and not checked:
        st.session_state["demo_selected"] = name
        st.rerun()
    if (not val) and checked:
        st.session_state["demo_selected"] = None
        st.rerun()

_demo_checkbox(c1, demo_names[0])
_demo_checkbox(c2, demo_names[1])
_demo_checkbox(c3, demo_names[2])
_demo_checkbox(c4, demo_names[3])

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
# Upload section
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

    pdf_path = run_out_dir / "harmonic_hunter_report.pdf"

    # BEFORE RUN: show what exists
    pre = {
        "csv_path": csv_path,
        "csv_exists": _exists(csv_path),
        "baseline_csv_path": baseline_csv_path,
        "baseline_exists": _exists(baseline_csv_path),
        "samples_dir": str(SAMPLES_DIR),
        "samples_dir_exists": SAMPLES_DIR.exists(),
        "uploads_dir": str(UPLOADS_DIR),
        "uploads_dir_exists": UPLOADS_DIR.exists(),
        "outputs_dir": str(OUTPUTS_DIR),
        "outputs_dir_exists": OUTPUTS_DIR.exists(),
        "run_out_dir": str(run_out_dir),
        "run_out_dir_exists": run_out_dir.exists(),
        "expected_pdf": str(pdf_path),
        "expected_pdf_exists_pre": pdf_path.exists(),
    }

    proc = None
    err = None

    with st.spinner("Running harmonic risk analysis…"):
        try:
            # Increase timeout if your report sometimes takes longer in cloud
            proc = run_cmd_with_logs(cmd, cwd=ROOT_DIR, timeout=900)
        except Exception as e:
            err = traceback.format_exc()

    # AFTER RUN: show outputs produced
    produced_files = []
    try:
        if run_out_dir.exists():
            produced_files = sorted([p.name for p in run_out_dir.glob("*")])
    except Exception:
        produced_files = ["<error listing output directory>"]

    post = {
        **pre,
        "return_code": getattr(proc, "returncode", None),
        "expected_pdf_exists_post": pdf_path.exists(),
        "produced_files": produced_files,
        "exception": err,
    }

    # Always show debug panel if PDF missing or return code non-zero or exception
    should_show_debug = (err is not None) or (proc is None) or (proc.returncode != 0) or (not pdf_path.exists())
    if should_show_debug:
        debug_panel(run_out_dir, cmd, proc, post)

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
        st.error("Report failed to generate. Open the Debug details panel above to see why.")

st.markdown('<div class="hr"></div>', unsafe_allow_html=True)
st.caption(
    "Advisory analysis based on exported electrical monitoring data. "
    "Not a substitute for on-site inspection or licensed engineering assessment."
)
