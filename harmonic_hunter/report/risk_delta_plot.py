from __future__ import annotations
import matplotlib.pyplot as plt


def plot_risk_delta(baseline: int, current: int, out_path: str):
    labels = ["Baseline", "Current"]
    values = [baseline, current]

    plt.figure(figsize=(4, 3))
    bars = plt.bar(labels, values)
    plt.ylim(0, 100)
    plt.ylabel("Risk Score (0–100)")
    plt.title("Facility Risk Change")

    for bar in bars:
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            height + 2,
            f"{int(height)}",
            ha="center",
            fontsize=9,
        )

    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()
