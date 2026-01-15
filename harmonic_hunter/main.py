from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, Literal, Tuple

import numpy as np
import typer

from harmonic_hunter.config import settings
from harmonic_hunter.ingest.csv_loader import load_csv
from harmonic_hunter.ingest.normalizer import normalize_timeseries

from harmonic_hunter.signal.fft_engine import per_phase_harmonics
from harmonic_hunter.signal.metrics import (
    thd_percent,
    triplen_index_percent,
    crest_factor,
    current_variability_percent,
)
from harmonic_hunter.signal.validity import estimate_sample_rate, fft_is_valid

from harmonic_hunter.risk.scoring import score_risk_fft, score_risk_trend
from harmonic_hunter.recommend.rules import (
    recommendations_fft,
    recommendations_trend,
    dedupe_preserve_order,
)

from harmonic_hunter.report.plots import plot_harmonic_spectrum, plot_current_timeseries
from harmonic_hunter.report.pdf_report import build_pdf_report
from harmonic_hunter.utils.logging import info, warn

app = typer.Typer(add_completion=False)

ReportKind = Literal["executive", "full"]


# -------------------------
# Helpers
# -------------------------
def _band_from_score(score: int) -> str:
    if score <= 30:
        return "Safe"
    if score <= 60:
        return "Monitor"
    if score <= 80:
        return "Action Required"
    return "Immediate Risk"


def _exec_verdict(score: int) -> str:
    if score <= 30:
        return (
            "No immediate power-quality risk detected. "
            "Observed load behavior is consistent with stable operation."
        )
    if score <= 60:
        return (
            "Early warning indicators detected. "
            "Continued monitoring is recommended to prevent escalation during peak demand or future expansion."
        )
    return (
        "Elevated power-quality risk detected. "
        "Observed conditions may contribute to equipment stress if left unaddressed."
    )


def _make_delta_chart(out_path: str, baseline_score: int, current_score: int):
    """Creates a small baseline vs current comparison chart for the PDF (matplotlib only)."""
    import matplotlib.pyplot as plt

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(4.4, 2.0), dpi=170)
    ax = fig.add_subplot(111)

    ax.bar(["Baseline", "Current"], [baseline_score, current_score])
    ax.set_ylim(0, 100)
    ax.set_ylabel("Risk score", fontsize=9)
    ax.tick_params(axis="both", labelsize=8)
    ax.set_title("Risk score comparison", fontsize=10)
    ax.grid(True, axis="y", alpha=0.25)

    plt.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def _safe_phase_order(phases: list[str]) -> list[str]:
    order = {"A": 0, "B": 1, "C": 2, "N": 3}
    return sorted(phases, key=lambda p: (order.get(str(p).upper(), 99), str(p)))


def _validate_and_clean(df):
    required = {"timestamp", "phase", "current_a"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df = df.copy()
    df["phase"] = df["phase"].astype(str)
    df = df.dropna(subset=["timestamp", "phase", "current_a"])

    df["current_a"] = np.asarray(df["current_a"], dtype=float)
    df = df[~np.isnan(df["current_a"])]

    try:
        df = df.sort_values("timestamp")
    except Exception:
        pass

    return df


def _compute_facility_score(df) -> Tuple[int, bool]:
    """
    Compute a facility score using FFT if valid, else trend mode.
    IMPORTANT: Only computes harmonics if fft_ok.
    Passes true sample_rate_hz into FFT.
    """
    sample_rate_hz = float(estimate_sample_rate(df))
    fft_ok = bool(fft_is_valid(sample_rate_hz, settings.fundamental_hz))

    phases = _safe_phase_order(sorted(df["phase"].astype(str).unique().tolist()))

    harms_by_phase = per_phase_harmonics(df, sample_rate_hz=sample_rate_hz) if fft_ok else {}

    scores: list[int] = []
    for phase in phases:
        sig = df[df["phase"].astype(str) == str(phase)]["current_a"].to_numpy(dtype=float)
        if sig.size < 8:
            continue

        cf = crest_factor(sig)
        var = current_variability_percent(sig)

        if fft_ok:
            harms = harms_by_phase.get(str(phase), {}) or harms_by_phase.get(phase, {})
            thd = thd_percent(harms)
            trip = triplen_index_percent(harms)
            i1 = harms.get(1, 0.0)
            fifth_pct = 0.0 if i1 <= 1e-12 else (harms.get(5, 0.0) / i1) * 100.0
            rr = score_risk_fft(thd=thd, triplen=trip, fifth_pct=fifth_pct)
        else:
            rr = score_risk_trend(crest=cf, variability=var)

        scores.append(rr.score_0_100)

    facility_score = int(round(float(np.mean(scores)))) if scores else 0
    return facility_score, fft_ok


def run_pipeline(
    csv_path: str,
    map_name: str = "auto",
    facility: str = "Unknown Facility",
    out_dir: str = "data/outputs",
    baseline_csv: Optional[str] = None,
    report_kind: ReportKind = "full",
) -> str:
    """
    Callable pipeline (for Streamlit). Returns path to PDF.
    Raises exceptions (so UI can show the real error).
    """
    out_dir_p = Path(out_dir)
    out_dir_p.mkdir(parents=True, exist_ok=True)

    run_log = out_dir_p / "run.log"

    def log(msg: str):
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{stamp}] {msg}"
        try:
            existing = run_log.read_text() if run_log.exists() else ""
            run_log.write_text(existing + line + "\n")
        except Exception:
            pass

    log(f"START run_pipeline | csv={csv_path} | map={map_name} | baseline={baseline_csv} | kind={report_kind}")

    # -------------------------
    # Load + normalize + validate
    # -------------------------
    t0 = time.time()
    df = normalize_timeseries(load_csv(csv_path, map_name=map_name))
    df = _validate_and_clean(df)
    log(f"Loaded+normalized rows={len(df)} in {time.time()-t0:.2f}s")

    sample_rate_hz = float(estimate_sample_rate(df))
    fft_ok = bool(fft_is_valid(sample_rate_hz, settings.fundamental_hz))
    report_mode = "Waveform FFT Mode" if fft_ok else "Trend Risk Mode (Log Cadence)"

    if not fft_ok:
        warn("Sampling rate too low for waveform FFT; using trend-risk indicators.")
        log("FFT invalid -> using trend mode")

    phases = _safe_phase_order(sorted(df["phase"].astype(str).unique().tolist()))
    log(f"Phases={phases} | sample_rate≈{sample_rate_hz:.2f}Hz")

    # ✅ Only compute harmonics if FFT is valid, and pass true sample rate
    harms_by_phase = {}
    if fft_ok:
        t1 = time.time()
        harms_by_phase = per_phase_harmonics(df, sample_rate_hz=sample_rate_hz)
        log(f"Computed harmonics in {time.time()-t1:.2f}s")

    # -------------------------
    # Per-phase analysis
    # -------------------------
    per_phase_scores: list[int] = []
    summary_lines: list[str] = [
        f"Estimated sampling rate: ~{sample_rate_hz:.2f} Hz",
        f"Analysis mode: {report_mode}",
    ]
    findings_all: list[str] = []
    top_risks_all: list[str] = []
    recs_all: list[str] = []
    images: list[str] = []

    for phase in phases:
        sig = df[df["phase"].astype(str) == str(phase)]["current_a"].to_numpy(dtype=float)
        if sig.size < 8:
            log(f"Phase {phase}: skipped (too few samples: {sig.size})")
            continue

        cf = crest_factor(sig)
        var = current_variability_percent(sig)

        # Always create timeseries chart
        ts_img = str(out_dir_p / f"timeseries_phase_{phase}.png")
        plot_current_timeseries(df, str(phase), ts_img, title=f"Phase {phase} — Current vs Time")
        images.append(ts_img)

        if fft_ok:
            harms = harms_by_phase.get(str(phase), {}) or harms_by_phase.get(phase, {})
            thd = thd_percent(harms)
            trip = triplen_index_percent(harms)
            i1 = harms.get(1, 0.0)
            fifth_pct = 0.0 if i1 <= 1e-12 else (harms.get(5, 0.0) / i1) * 100.0

            risk = score_risk_fft(thd=thd, triplen=trip, fifth_pct=fifth_pct)
            recs = recommendations_fft(thd=thd, triplen=trip, fifth_pct=fifth_pct)

            summary_lines.append(
                f"Phase {phase}: Risk {risk.score_0_100}/100 ({risk.band}) | "
                f"THD {thd:.1f}% | Triplen {trip:.1f}% | 5th {fifth_pct:.1f}% | "
                f"Crest {cf:.2f} | Variability {var:.1f}%"
            )

            spec_img = str(out_dir_p / f"spectrum_phase_{phase}.png")
            plot_harmonic_spectrum(harms, spec_img, title=f"Phase {phase} — Harmonic Spectrum")
            images.append(spec_img)

        else:
            risk = score_risk_trend(crest=cf, variability=var)
            recs = recommendations_trend(crest=cf, variability=var)

            summary_lines.append(
                f"Phase {phase}: Risk {risk.score_0_100}/100 ({risk.band}) | "
                f"Crest {cf:.2f} | Variability {var:.1f}%"
            )

        per_phase_scores.append(risk.score_0_100)
        recs_all.extend(recs)
        findings_all.extend([f"Phase {phase}: {f}" for f in (risk.findings or [])])
        top_risks_all.extend([f"Phase {phase}: {r}" for r in (risk.top_risks or [])])

    # -------------------------
    # Facility aggregation
    # -------------------------
    facility_score = int(round(float(np.mean(per_phase_scores)))) if per_phase_scores else 0
    band = _band_from_score(facility_score)
    executive_verdict = _exec_verdict(facility_score)

    why_lines = [
        "Observed current behavior reflects non-linear electrical loading patterns.",
        "Phase-level variability suggests uneven load distribution across monitored circuits.",
    ]

    recs_all = dedupe_preserve_order(recs_all)
    top_risks = dedupe_preserve_order(top_risks_all)[:4]

    summary_lines.insert(0, f"Facility risk score: {facility_score}/100 ({band})")

    if report_kind == "full":
        summary_lines.extend(findings_all[:18])
    else:
        summary_lines.extend(findings_all[:6])

    # -------------------------
    # Baseline comparison
    # -------------------------
    baseline_score = None
    risk_delta = None
    delta_chart_path = None
    change_summary: Optional[str] = None

    if baseline_csv:
        try:
            base_df = normalize_timeseries(load_csv(baseline_csv, map_name=map_name))
            base_df = _validate_and_clean(base_df)

            # ✅ compute baseline score with its OWN cadence
            baseline_score, _ = _compute_facility_score(base_df)
            risk_delta = facility_score - baseline_score

            delta_chart_path = str(out_dir_p / "risk_delta.png")
            _make_delta_chart(delta_chart_path, baseline_score, facility_score)

            if risk_delta > 0:
                change_summary = f"Overall risk increased from {baseline_score} → {facility_score} (Δ +{risk_delta})."
            elif risk_delta < 0:
                change_summary = f"Overall risk decreased from {baseline_score} → {facility_score} (Δ {risk_delta})."
            else:
                change_summary = f"Overall risk is unchanged at {facility_score}/100."

            log(f"Baseline ok: baseline={baseline_score} delta={risk_delta}")

        except Exception as e:
            warn(f"Baseline comparison failed: {e}")
            log(f"Baseline failed: {repr(e)}")

    # -------------------------
    # Build PDF
    # -------------------------
    out_pdf = str(out_dir_p / "harmonic_hunter_report.pdf")
    build_pdf_report(
        out_pdf=out_pdf,
        facility_name=facility,
        report_mode=report_mode,
        risk_score=facility_score,
        risk_band=band,
        baseline_score=baseline_score,
        risk_delta=risk_delta,
        change_summary=change_summary,
        executive_verdict=executive_verdict,
        why_lines=why_lines,
        key_observations=top_risks or ["No critical risk indicators identified."],
        recommendations=recs_all[:10],
        summary_lines=summary_lines,
        images=images if report_kind == "full" else (images[:3] if images else []),
        delta_chart_path=delta_chart_path,
        report_kind=report_kind,
    )

    log(f"DONE | pdf={out_pdf}")
    return out_pdf


# -------------------------
# Typer CLI wrapper
# -------------------------
@app.command()
def run(
    csv_path: str = typer.Argument(..., help="Path to CSV export from PDU/UPS"),
    map_name: str = typer.Option("auto", help="Column mapping template"),
    facility: str = typer.Option("Unknown Facility", help="Facility name shown in report"),
    out_dir: str = typer.Option("data/outputs", help="Output folder"),
    baseline_csv: Optional[str] = typer.Option(None, help="Optional baseline CSV for risk delta comparison"),
    report_kind: ReportKind = typer.Option("full", help="executive|full"),
):
    out_pdf = run_pipeline(
        csv_path=csv_path,
        map_name=map_name,
        facility=facility,
        out_dir=out_dir,
        baseline_csv=baseline_csv,
        report_kind=report_kind,
    )
    info(f"Report generated: {out_pdf}")


if __name__ == "__main__":
    app()
