"""Flag detections that are probably not vegetation fires."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .places import haversine_km


# FIRMS archive (standard processing) "type" values.
FIRMS_TYPES = {
    0: "",  # presumed vegetation fire
    1: "Active volcano (FIRMS)",
    2: "Other static land source (FIRMS)",
    3: "Offshore (FIRMS)",
}
KNOWN_SOURCE_COLUMNS = ["name", "latitude", "longitude", "radius_km", "kind"]


def load_known_sources(path: str | Path) -> pd.DataFrame:
    """Load the team's list of known non-fire heat sources (CSV)."""
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=KNOWN_SOURCE_COLUMNS)
    sources = pd.read_csv(path, comment="#")
    missing = set(KNOWN_SOURCE_COLUMNS) - set(sources.columns)
    if missing:
        raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
    return sources[KNOWN_SOURCE_COLUMNS].dropna(subset=["latitude", "longitude"])


def flag_false_alarms(
    observations: pd.DataFrame, known_sources: pd.DataFrame
) -> pd.DataFrame:
    """Add ``false_alarm_reason`` ("" for detections that look like fires)."""
    observations = observations.copy()
    reasons = pd.Series("", index=observations.index, dtype=object)

    if "type" in observations:
        types = pd.to_numeric(observations["type"], errors="coerce")
        reasons = reasons.mask(types.isin([1, 2, 3]), types.map(FIRMS_TYPES))

    latitudes = observations["latitude"].to_numpy(dtype=float)
    longitudes = observations["longitude"].to_numpy(dtype=float)
    for source in known_sources.itertuples():
        radius = float(source.radius_km) if pd.notna(source.radius_km) else 1.0
        near = haversine_km(latitudes, longitudes, source.latitude, source.longitude)
        hit = (near <= radius) & (reasons == "").to_numpy()
        kind = source.kind if isinstance(source.kind, str) and source.kind else ""
        label = f"{kind}: {source.name}" if kind else str(source.name)
        reasons.iloc[np.flatnonzero(hit)] = label

    observations["false_alarm_reason"] = reasons
    return observations
