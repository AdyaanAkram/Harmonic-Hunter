from __future__ import annotations

from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


def _format_secs(x, _pos=None) -> str:
    """Seconds -> '0s', '12s', '1:05'."""
    if x is None:
        return ""
    try:
        x = float(x)
    except Exception:
        return ""
    if x < 0:
        x = 0.0
    s = int(round(x))
    if s >= 60:
        return f"{s//60}:{s%60:02d}"
    return f"{s}s"


def plot_current_timeseries(df, phase: str, out_path: str, title: str):
    """
    Creates a compact, PDF-friendly time-series chart.
    X-axis is relative time (seconds) to avoid long datetime/timedelta labels.
    """
    out_path = str(out_path)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    d = df[df["phase"].astype(str) == str(phase)].copy()
    if d.empty:
        fig = plt.figure(figsize=(6.6, 2.6), dpi=160)
        ax = fig.add_subplot(111)
        ax.set_title(title, fontsize=11)
        ax.text(0.5, 0.5, "No data for this phase", ha="center", va="center", fontsize=10)
        ax.set_axis_off()
        plt.tight_layout()
        fig.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        return

    ts = d["timestamp"]

    # Try datetime
    ts_dt = pd.to_datetime(ts, errors="coerce")
    if not ts_dt.isna().all():
        x = (ts_dt - ts_dt.iloc[0]).dt.total_seconds()
        xlabel = "Time"
    # Try timedelta
    elif pd.api.types.is_timedelta64_dtype(ts):
        x = (ts - ts.iloc[0]).dt.total_seconds()
        xlabel = "Time"
    else:
        # Fallback: index
        x = range(len(d))
        xlabel = "Sample"

    fig = plt.figure(figsize=(6.6, 2.6), dpi=160)
    ax = fig.add_subplot(111)

    ax.plot(x, d["current_a"], linewidth=1.8)
    ax.set_title(title, fontsize=11, pad=10)
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel("Current (A)", fontsize=9)

    # Fewer ticks + cleaner labels
    ax.xaxis.set_major_locator(mticker.MaxNLocator(nbins=5, integer=True))
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_format_secs))

    ax.tick_params(axis="both", labelsize=8)
    ax.grid(True, alpha=0.25)

    plt.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def plot_harmonic_spectrum(harmonics: dict[int, float], out_path: str, title: str):
    """
    Bar chart, compact and PDF-friendly.
    """
    out_path = str(out_path)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    orders = sorted(harmonics.keys())
    amps = [harmonics[k] for k in orders]

    fig = plt.figure(figsize=(6.6, 2.6), dpi=160)
    ax = fig.add_subplot(111)

    ax.bar([str(o) for o in orders], amps)
    ax.set_title(title, fontsize=11, pad=10)
    ax.set_xlabel("Harmonic order", fontsize=9)
    ax.set_ylabel("Amplitude (A)", fontsize=9)
    ax.tick_params(axis="both", labelsize=8)
    ax.grid(True, axis="y", alpha=0.25)

    plt.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
