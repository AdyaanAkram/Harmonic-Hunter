from __future__ import annotations

import numpy as np


def thd_percent(harmonics: dict[int, float]) -> float:
    """
    THD = sqrt(sum(h>1 Ih^2)) / I1 * 100
    Using extracted magnitudes as proxy for Ih.
    """
    i1 = float(harmonics.get(1, 0.0))
    if i1 <= 1e-12:
        return 0.0
    s = 0.0
    for h, mag in harmonics.items():
        if h != 1:
            s += float(mag) ** 2
    return (np.sqrt(s) / i1) * 100.0


def triplen_index_percent(harmonics: dict[int, float]) -> float:
    """
    Triplen harmonics: multiples of 3 (3, 9, 15...)
    Index = sqrt(sum(triplen^2)) / I1 * 100
    """
    i1 = float(harmonics.get(1, 0.0))
    if i1 <= 1e-12:
        return 0.0
    s = 0.0
    for h, mag in harmonics.items():
        if h % 3 == 0 and h != 0:
            s += float(mag) ** 2
    return (np.sqrt(s) / i1) * 100.0


def crest_factor(signal: np.ndarray) -> float:
    """
    Crest factor = peak / RMS
    """
    if signal.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(signal * signal)))
    if rms <= 1e-12:
        return 0.0
    peak = float(np.max(np.abs(signal)))
    return peak / rms


def current_variability_percent(signal: np.ndarray) -> float:
    """
    Coefficient of variation (%) = std/mean * 100.
    High values are consistent with pulsed/non-linear loads.
    """
    if signal.size == 0:
        return 0.0
    mean = float(np.mean(signal))
    if abs(mean) <= 1e-12:
        return 0.0
    std = float(np.std(signal))
    return (std / abs(mean)) * 100.0
