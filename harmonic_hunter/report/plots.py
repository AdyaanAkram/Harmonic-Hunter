from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt


def plot_current_timeseries(df, phase: str, out_path: str, title: str):
    """
    Expected signature (used throughout the project):
      plot_current_timeseries(df, phase, out_path, title)

    Creates a compact, PDF-friendly time-series chart with smaller tick labels.
    """
    out_path = str(out_path)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    d = df[df["phase"].astype(str) == str(phase)].copy()
    if d.empty:
        # still write an empty chart so the PDF pipeline doesn't break
        fig = plt.figure(figsize=(6.6, 2.6), dpi=160)
        ax = fig.add_subplot(111)
        ax.set_title(title, fontsize=11)
        ax.text(0.5, 0.5, "No data for this phase", ha="center", va="center", fontsize=10)
        ax.set_axis_off()
        plt.tight_layout()
        fig.savefig(out_path, bbox_inches="tight")
        plt.close(fig)
        return

    fig = plt.figure(figsize=(6.6, 2.6), dpi=160)
    ax = fig.add_subplot(111)

    ax.plot(d["timestamp"], d["current_a"], linewidth=1.8)
    ax.set_title(title, fontsize=11, pad=10)
    ax.set_xlabel("Time", fontsize=9)
    ax.set_ylabel("Current (A)", fontsize=9)

    # Smaller ticks + less clutter
    ax.tick_params(axis="both", labelsize=8)
    for label in ax.get_xticklabels():
        label.set_rotation(0)
        label.set_ha("center")

    ax.grid(True, alpha=0.25)
    plt.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def plot_harmonic_spectrum(harmonics: dict[int, float], out_path: str, title: str):
    """
    Expected signature:
      plot_harmonic_spectrum(harmonics, out_path, title)

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
