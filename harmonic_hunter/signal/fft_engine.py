from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.fft import rfft, rfftfreq

from harmonic_hunter.config import settings


def compute_fft_harmonics(
    current: np.ndarray,
    sample_rate_hz: float,
) -> dict[int, float]:
    """
    Returns harmonic magnitudes at n*fundamental.
    Uses Hann window to reduce spectral leakage.
    Magnitudes are "relative amplitude" and consistent across phases/runs.
    """
    x = np.asarray(current, dtype=float)
    x = x[np.isfinite(x)]

    n = int(x.size)
    if n < 32 or sample_rate_hz <= 0:
        return {h: 0.0 for h in settings.harmonics}

    # Remove DC
    x = x - float(np.mean(x))

    # Windowing (reduces leakage)
    w = np.hanning(n)
    xw = x * w

    yf = rfft(xw)
    xf = rfftfreq(n, d=1.0 / float(sample_rate_hz))

    mags = np.abs(yf)

    # Normalize by window power so amplitudes are comparable
    # This isn't perfect RMS, but is stable and consistent for scoring.
    w_norm = np.sum(w) / 2.0
    if w_norm > 1e-12:
        mags = mags / w_norm
    else:
        mags = mags / n

    def magnitude_at(freq: float) -> float:
        idx = int(np.argmin(np.abs(xf - freq)))
        return float(mags[idx])

    out: dict[int, float] = {}
    for h in settings.harmonics:
        out[h] = magnitude_at(float(h) * float(settings.fundamental_hz))
    return out


def per_phase_harmonics(df: pd.DataFrame, sample_rate_hz: float | None = None) -> dict[str, dict[int, float]]:
    """
    df columns: timestamp, phase, current_a.
    If sample_rate_hz is not provided, falls back to 1/settings.resample_seconds.
    (Better: pass the true estimate from timestamps.)
    """
    sr = float(sample_rate_hz) if sample_rate_hz and sample_rate_hz > 0 else (1.0 / float(settings.resample_seconds))

    results: dict[str, dict[int, float]] = {}
    for phase, g in df.groupby("phase"):
        current = g["current_a"].to_numpy(dtype=float)
        results[str(phase)] = compute_fft_harmonics(current, sr)
    return results
