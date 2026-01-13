from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.fft import rfft, rfftfreq

from harmonic_hunter.config import settings

def compute_fft_harmonics(current: np.ndarray, sample_rate_hz: float) -> dict[int, float]:
    """
    Returns harmonic magnitudes (RMS-ish scaled) at n*fundamental.
    """
    n = len(current)
    # Remove DC offset
    x = current - np.mean(current)

    yf = rfft(x)
    xf = rfftfreq(n, d=1.0 / sample_rate_hz)

    mags = np.abs(yf) / n  # amplitude scale

    def magnitude_at(freq: float) -> float:
        idx = int(np.argmin(np.abs(xf - freq)))
        return float(mags[idx])

    out = {}
    for h in settings.harmonics:
        out[h] = magnitude_at(h * settings.fundamental_hz)
    return out

def per_phase_harmonics(df: pd.DataFrame) -> dict[str, dict[int, float]]:
    """
    df columns: timestamp, phase, current_a. Must be uniform cadence.
    """
    # Estimate sample rate from resample_seconds
    sample_rate_hz = 1.0 / settings.resample_seconds

    results: dict[str, dict[int, float]] = {}
    for phase, g in df.groupby("phase"):
        current = g["current_a"].to_numpy(dtype=float)
        results[str(phase)] = compute_fft_harmonics(current, sample_rate_hz)
    return results
