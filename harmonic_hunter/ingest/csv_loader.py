from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

from harmonic_hunter.utils.logging import info, warn


@dataclass
class ColumnMap:
    timestamp: str
    current_a: str
    phase: str | None = None


# Known “templates” (add as you see new exports)
KNOWN_MAPS: dict[str, ColumnMap] = {
    "default": ColumnMap(timestamp="timestamp", current_a="current_a", phase="phase"),
    "apc_like": ColumnMap(timestamp="Time", current_a="Current", phase="Phase"),
    "vertiv_like": ColumnMap(timestamp="Timestamp", current_a="I(A)", phase="Phase"),
    "eaton_like": ColumnMap(timestamp="Date/Time", current_a="Current (A)", phase="Phase"),
}

# Auto-detect candidates (common vendor names)
TS_CANDIDATES = [
    "timestamp", "time", "datetime", "date/time", "date time", "Date/Time", "Time", "Timestamp"
]
PHASE_CANDIDATES = ["phase", "Phase", "PHASE", "leg", "Leg", "L"]
CURRENT_CANDIDATES = [
    "current_a", "current", "Current", "I(A)", "I (A)", "Current (A)", "amps", "Amps", "A"
]


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols_lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        key = cand.lower()
        if key in cols_lower:
            return cols_lower[key]
    return None


def autodetect_map(df: pd.DataFrame) -> ColumnMap:
    ts = _find_col(df, TS_CANDIDATES)
    cur = _find_col(df, CURRENT_CANDIDATES)
    ph = _find_col(df, PHASE_CANDIDATES)

    if not ts or not cur:
        raise ValueError(
            "Auto-detect failed. CSV must include a timestamp and current column. "
            f"Columns found: {list(df.columns)}"
        )
    return ColumnMap(timestamp=ts, current_a=cur, phase=ph)


def load_csv(path: str, map_name: str = "auto") -> pd.DataFrame:
    """
    Returns standardized dataframe with columns:
      - timestamp (datetime)
      - current_a (float)
      - phase (str)
    """
    info(f"Loading CSV: {path}")
    df = pd.read_csv(path)

    if map_name == "auto":
        cmap = autodetect_map(df)
        info(f"Auto-detected columns: timestamp='{cmap.timestamp}', current='{cmap.current_a}', phase='{cmap.phase}'")
    else:
        if map_name not in KNOWN_MAPS:
            raise ValueError(f"Unknown map_name='{map_name}'. Options: {['auto'] + list(KNOWN_MAPS.keys())}")
        cmap = KNOWN_MAPS[map_name]

    missing = [c for c in [cmap.timestamp, cmap.current_a] if c not in df.columns]
    if missing:
        warn(f"CSV columns found: {list(df.columns)}")
        raise ValueError(f"Missing required columns for map '{map_name}': {missing}")

    out = pd.DataFrame()
    out["timestamp"] = pd.to_datetime(df[cmap.timestamp], errors="coerce")
    out["current_a"] = pd.to_numeric(df[cmap.current_a], errors="coerce")

    if cmap.phase and cmap.phase in df.columns:
        out["phase"] = df[cmap.phase].astype(str).fillna("A")
    else:
        out["phase"] = "A"

    out = out.dropna(subset=["timestamp", "current_a"]).sort_values("timestamp").reset_index(drop=True)
    info(f"Loaded {len(out):,} valid rows.")
    return out
