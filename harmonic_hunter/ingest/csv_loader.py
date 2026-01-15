from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from harmonic_hunter.utils.logging import info, warn


@dataclass
class ColumnMap:
    timestamp: str
    current_a: str
    phase: Optional[str] = None


KNOWN_MAPS: dict[str, ColumnMap] = {
    "default": ColumnMap(timestamp="timestamp", current_a="current_a", phase="phase"),
    "apc_like": ColumnMap(timestamp="Time", current_a="Current", phase="Phase"),
    "vertiv_like": ColumnMap(timestamp="Timestamp", current_a="I(A)", phase="Phase"),
    "eaton_like": ColumnMap(timestamp="Date/Time", current_a="Current (A)", phase="Phase"),
}

# Common vendor names (case-insensitive matching)
TS_CANDIDATES = [
    "timestamp", "time", "datetime", "date/time", "date time", "date", "time stamp", "Time", "Timestamp", "Date/Time"
]
PHASE_CANDIDATES = [
    "phase", "leg", "line", "pole"  # avoid overly-generic single-letter candidates
]
CURRENT_CANDIDATES = [
    "current_a", "current", "i(a)", "i (a)", "amps", "amperes", "a", "Current", "Current (A)", "I(A)"
]

# If there's no phase column, we can infer phases from wide columns like:
# Current_A, Current_B, Current_C, Ia, Ib, Ic, I(A)_A ...
WIDE_CURRENT_PATTERNS = [
    ("a", ["current_a", "current a", "ia", "i_a", "i(a)_a", "amps_a", "a current"]),
    ("b", ["current_b", "current b", "ib", "i_b", "i(a)_b", "amps_b", "b current"]),
    ("c", ["current_c", "current c", "ic", "i_c", "i(a)_c", "amps_c", "c current"]),
]


def _clean_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _lower_map(cols) -> dict[str, str]:
    return {str(c).strip().lower(): str(c).strip() for c in cols}


def _find_col(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    cols_lower = _lower_map(df.columns)
    for cand in candidates:
        key = str(cand).strip().lower()
        if key in cols_lower:
            return cols_lower[key]
    return None


def _score_col_name(name: str, candidates: list[str]) -> int:
    """Simple scoring: exact match > contains match."""
    n = name.strip().lower()
    score = 0
    for cand in candidates:
        c = str(cand).strip().lower()
        if n == c:
            score += 10
        elif c in n:
            score += 3
    return score


def _best_match(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    """Choose best-scoring column name among all columns."""
    best = None
    best_score = 0
    for col in df.columns:
        s = _score_col_name(str(col), candidates)
        if s > best_score:
            best_score = s
            best = str(col)
    return best if best_score > 0 else None


def autodetect_map(df: pd.DataFrame) -> ColumnMap:
    # Prefer exact candidate matches first
    ts = _find_col(df, TS_CANDIDATES) or _best_match(df, TS_CANDIDATES)
    cur = _find_col(df, CURRENT_CANDIDATES) or _best_match(df, CURRENT_CANDIDATES)
    ph = _find_col(df, PHASE_CANDIDATES) or _best_match(df, PHASE_CANDIDATES)

    if not ts or not cur:
        raise ValueError(
            "Auto-detect failed. CSV must include a timestamp and current column.\n"
            f"Columns found: {list(df.columns)}"
        )
    return ColumnMap(timestamp=ts, current_a=cur, phase=ph)


def _try_read_csv(path: str) -> pd.DataFrame:
    """
    Vendor exports can be weird (encoding/separators).
    Try a few safe options.
    """
    # First: normal read
    try:
        return pd.read_csv(path)
    except Exception:
        pass

    # Try separator autodetect
    try:
        return pd.read_csv(path, sep=None, engine="python")
    except Exception:
        pass

    # Try common encodings
    for enc in ("utf-8", "utf-8-sig", "latin1"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue

    # Last resort: let pandas raise the last error
    return pd.read_csv(path)


def _coerce_current(series: pd.Series) -> pd.Series:
    """
    Turn values like '11.2 A' or '11,2' into numeric.
    """
    s = series.astype(str).str.strip()
    s = s.str.replace(",", ".", regex=False)
    s = s.str.replace("A", "", regex=False).str.replace("amps", "", regex=False).str.strip()
    return pd.to_numeric(s, errors="coerce")


def _parse_timestamp(series: pd.Series) -> pd.Series:
    """
    Handle typical timestamp weirdness:
    - ISO strings
    - '2026-01-01 12:00:00'
    - Excel numbers (rare but happens)
    """
    # Try normal parse
    ts = pd.to_datetime(series, errors="coerce", infer_datetime_format=True)

    # If everything failed, try Excel serial numbers (days since 1899-12-30)
    if ts.isna().all():
        num = pd.to_numeric(series, errors="coerce")
        if num.notna().any():
            ts = pd.to_datetime("1899-12-30") + pd.to_timedelta(num, unit="D")

    return ts


def _infer_wide_phase_columns(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    If CSV has no phase column but has separate current columns per phase,
    convert to long format: timestamp, phase, current_a.
    """
    cols_lower = _lower_map(df.columns)

    # Find timestamp col first
    ts_col = _find_col(df, TS_CANDIDATES) or _best_match(df, TS_CANDIDATES)
    if not ts_col:
        return None

    # Identify current columns per phase
    found = {}
    for phase, patterns in WIDE_CURRENT_PATTERNS:
        for p in patterns:
            if p.lower() in cols_lower:
                found[phase.upper()] = cols_lower[p.lower()]
                break

    # Need at least 2 phases to consider it a real wide format
    if len(found) < 2:
        return None

    out_rows = []
    ts = _parse_timestamp(df[ts_col])
    for ph, cur_col in found.items():
        cur = _coerce_current(df[cur_col])
        tmp = pd.DataFrame({"timestamp": ts, "phase": ph, "current_a": cur})
        out_rows.append(tmp)

    out = pd.concat(out_rows, ignore_index=True)
    return out


def load_csv(path: str, map_name: str = "auto") -> pd.DataFrame:
    """
    Returns standardized dataframe with columns:
      - timestamp (datetime)
      - current_a (float)
      - phase (str)
    """
    info(f"Loading CSV: {path}")
    df = _try_read_csv(path)
    df = _clean_cols(df)

    # Wide-phase inference first (only when auto)
    if map_name == "auto":
        wide = _infer_wide_phase_columns(df)
        if wide is not None:
            info("Detected wide per-phase current columns; converting to long format.")
            out = wide
            out = out.dropna(subset=["timestamp", "current_a"]).sort_values("timestamp").reset_index(drop=True)
            out["phase"] = out["phase"].astype(str)
            info(f"Loaded {len(out):,} valid rows (wide->long).")
            return out

    # Map-based parsing
    if map_name == "auto":
        cmap = autodetect_map(df)
        info(
            f"Auto-detected columns: timestamp='{cmap.timestamp}', "
            f"current='{cmap.current_a}', phase='{cmap.phase}'"
        )
    else:
        if map_name not in KNOWN_MAPS:
            raise ValueError(f"Unknown map_name='{map_name}'. Options: {['auto'] + list(KNOWN_MAPS.keys())}")
        cmap = KNOWN_MAPS[map_name]

    missing = [c for c in [cmap.timestamp, cmap.current_a] if c not in df.columns]
    if missing:
        warn(f"CSV columns found: {list(df.columns)}")
        raise ValueError(f"Missing required columns for map '{map_name}': {missing}")

    out = pd.DataFrame()
    out["timestamp"] = _parse_timestamp(df[cmap.timestamp])
    out["current_a"] = _coerce_current(df[cmap.current_a])

    if cmap.phase and cmap.phase in df.columns:
        out["phase"] = df[cmap.phase].astype(str).fillna("A")
        # Clean common phase formats like "Phase A" -> "A"
        out["phase"] = out["phase"].str.replace("phase", "", case=False).str.strip()
    else:
        out["phase"] = "A"

    out = out.dropna(subset=["timestamp", "current_a"])
    out = out.sort_values("timestamp").reset_index(drop=True)

    if out.empty:
        raise ValueError(
            "No valid rows after parsing. Check timestamp/current formatting.\n"
            f"Columns: {list(df.columns)}"
        )

    info(f"Loaded {len(out):,} valid rows.")
    return out
