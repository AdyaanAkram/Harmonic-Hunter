from __future__ import annotations

import pandas as pd

from harmonic_hunter.config import settings
from harmonic_hunter.utils.logging import info, warn


def normalize_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    """
    Input: columns [timestamp, phase, current_a]
    Output: uniform cadence per-phase, interpolated current_a
    """
    info("Normalizing time series (resample + interpolation).")

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    out_frames: list[pd.DataFrame] = []
    rule = f"{int(settings.resample_seconds)}s"

    for phase, g in df.groupby("phase"):
        g = g.set_index("timestamp").sort_index()

        # resample numeric only
        rg_num = g[["current_a"]].resample(rule).mean()

        # fill gaps
        rg_num["current_a"] = rg_num["current_a"].interpolate(limit_direction="both")

        rg = rg_num
        rg["phase"] = str(phase)

        if len(rg) < 32:
            warn(f"Phase {phase}: only {len(rg)} samples after resample; FFT may be unstable.")

        out_frames.append(rg.reset_index())

    out = pd.concat(out_frames, ignore_index=True)
    info(f"Normalized rows: {len(out):,}")
    return out
