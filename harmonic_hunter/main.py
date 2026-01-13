from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

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
            "Continued monitoring recommended to prevent escalation during peak demand or future expansion."
        )
    return (
        "Elevated power-quality risk detected. "
        "Observed conditions may contribute to equipment stress if left unaddressed."
    )


def _make_delta_chart(out_path: str, baseline_score: int, current_score: int):
    """
    Creates a tiny baseline vs current comparison chart for the PDF (no seaborn).
    """
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


@app.command()
def run(
    csv_path: str = typer.Argument(..., help="Path to CSV export from PDU/UPS"),
    map_name: str = typer.Option("auto", help="Column mapping template"),
    facility: str = typer.Option("Unknown Facility", help="Facility name shown in report"),
    out_dir: str = typer.Option("data/outputs", help="Output folder"),
    baseline_csv: Optional[str] = typer.Option(None, help="Optional baseline CSV for risk delta comparison"),
):
    os.makedirs(out_dir, exist_ok=True)

    # -------------------------
    # Load + normalize
    # -------------------------
    df = normalize_timeseries(load_csv(csv_path, map_name=map_name))

    sample_rate_hz = float(estimate_sample_rate(df))
    fft_ok = bool(fft_is_valid(sample_rate_hz, settings.fundamental_hz))
    report_mode = "Waveform FFT Mode" if fft_ok else "Trend Risk Mode (Log Cadence)"

    if not fft_ok:
        warn("Sampling rate too low for waveform FFT; using trend-risk indicators.")

    harms_by_phase = per_phase_harmonics(df)  # ok even if trend mode; used only if fft_ok

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

    # Ensure deterministic ordering A/B/C if present
    phases = sorted(harms_by_phase.keys(), key=lambda p: str(p))

    for phase in phases:
        harms = harms_by_phase.get(phase, {})
        sig = df[df["phase"].astype(str) == str(phase)]["current_a"].to_numpy(dtype=float)

        cf = crest_factor(sig)
        var = current_variability_percent(sig)

        # Always create timeseries chart
        ts_img = os.path.join(out_dir, f"timeseries_phase_{phase}.png")
        plot_current_timeseries(df, str(phase), ts_img, title=f"Phase {phase} — Current vs Time")
        images.append(ts_img)

        if fft_ok:
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

            spec_img = os.path.join(out_dir, f"spectrum_phase_{phase}.png")
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

    # Why lines: short + defensible
    why_lines = [
        "Observed current behavior reflects non-linear electrical loading patterns.",
        "Phase-level variability suggests uneven load distribution across monitored circuits.",
    ]

    recs_all = dedupe_preserve_order(recs_all)
    top_risks = dedupe_preserve_order(top_risks_all)[:4]

    # Put the facility summary first
    summary_lines.insert(0, f"Facility risk score: {facility_score}/100 ({band})")
    summary_lines.extend(findings_all[:12])  # keep technical section useful but not infinite

    # -------------------------
    # Baseline comparison
    # -------------------------
    baseline_score = None
    risk_delta = None
    delta_chart_path = None

    if baseline_csv:
        try:
            base_df = normalize_timeseries(load_csv(baseline_csv, map_name=map_name))
            base_sr = float(estimate_sample_rate(base_df))
            base_fft_ok = bool(fft_is_valid(base_sr, settings.fundamental_hz))
            base_harms = per_phase_harmonics(base_df)

            base_scores: list[int] = []
            for phase in sorted(base_harms.keys(), key=lambda p: str(p)):
                harms = base_harms.get(phase, {})
                sig = base_df[base_df["phase"].astype(str) == str(phase)]["current_a"].to_numpy(dtype=float)
                cf = crest_factor(sig)
                var = current_variability_percent(sig)

                if base_fft_ok:
                    thd = thd_percent(harms)
                    trip = triplen_index_percent(harms)
                    i1 = harms.get(1, 0.0)
                    fifth_pct = 0.0 if i1 <= 1e-12 else (harms.get(5, 0.0) / i1) * 100.0
                    rr = score_risk_fft(thd=thd, triplen=trip, fifth_pct=fifth_pct)
                else:
                    rr = score_risk_trend(crest=cf, variability=var)

                base_scores.append(rr.score_0_100)

            baseline_score = int(round(float(np.mean(base_scores)))) if base_scores else 0
            risk_delta = facility_score - baseline_score

            delta_chart_path = os.path.join(out_dir, "risk_delta.png")
            _make_delta_chart(delta_chart_path, baseline_score, facility_score)
        except Exception as e:
            warn(f"Baseline comparison failed: {e}")

    # -------------------------
    # Build PDF
    # -------------------------
    out_pdf = os.path.join(out_dir, "harmonic_hunter_report.pdf")
    build_pdf_report(
        out_pdf=out_pdf,
        facility_name=facility,
        report_mode=report_mode,
        risk_score=facility_score,
        risk_band=band,
        baseline_score=baseline_score,
        risk_delta=risk_delta,
        executive_verdict=executive_verdict,
        why_lines=why_lines,
        key_observations=top_risks or ["No critical risk indicators identified."],
        recommendations=recs_all[:10],
        summary_lines=summary_lines,
        images=images,
        delta_chart_path=delta_chart_path,
    )

    info(f"Report generated: {out_pdf}")


if __name__ == "__main__":
    app()
