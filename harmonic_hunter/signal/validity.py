from __future__ import annotations

import pandas as pd


def estimate_sample_rate(df: pd.DataFrame) -> float:
    """
    Estimate sample rate (Hz) from median timestamp delta.
    Works on already-normalized data too.
    """
    ts = pd.to_datetime(df["timestamp"]).sort_values()
    if len(ts) < 3:
        return 0.0

    deltas = ts.diff().dt.total_seconds().dropna()
    if deltas.empty:
        return 0.0

    median_dt = float(deltas.median())
    if median_dt <= 0:
        return 0.0
    return 1.0 / median_dt


def fft_is_valid(sample_rate_hz: float, fundamental_hz: float = 60.0) -> bool:
    """
    True waveform FFT needs sample_rate well above highest frequency of interest.
    Rule of thumb: sample_rate >= 20x fundamental (still conservative).
    """
    return sample_rate_hz >= 20.0 * fundamental_hz
