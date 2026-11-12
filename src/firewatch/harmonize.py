from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "id",
    "source",
    "observed_at",
    "latitude",
    "longitude",
    "confidence",
}


@dataclass(frozen=True)
class MatchConfig:
    max_minutes: int = 30
    max_distance_km: float = 5.0


def validate_schema(data: pd.DataFrame) -> None:
    """Raise a useful error when an input dataset misses required fields."""
    missing = REQUIRED_COLUMNS.difference(data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    if not data["source"].isin({"MODIS", "VIIRS"}).all():
        raise ValueError("source must contain only MODIS or VIIRS")
    if not data["latitude"].between(-90, 90).all():
        raise ValueError("latitude must be between -90 and 90")
    if not data["longitude"].between(-180, 180).all():
        raise ValueError("longitude must be between -180 and 180")


def _distance_km(
    latitude: float,
    longitude: float,
    other_latitudes: np.ndarray,
    other_longitudes: np.ndarray,
) -> np.ndarray:
    """Approximate distance for the small regional distances in this MVP."""
    latitude_km = (latitude - other_latitudes) * 111.0
    longitude_km = (longitude - other_longitudes) * 111.0 * cos(radians(latitude))
    return np.sqrt(latitude_km**2 + longitude_km**2)


def _find_candidates(
    data: pd.DataFrame, config: MatchConfig
) -> list[tuple[float, float, int, int]]:
    """Return (distance_km, minutes, modis_position, viirs_position) pairs.

    VIIRS records are sorted by time so each MODIS record is only compared
    with VIIRS records inside its time window, instead of with every record.
    """
    sources = data["source"].to_numpy()
    times_ns = (
        data["observed_at"]
        .dt.tz_convert("UTC")
        .dt.tz_localize(None)
        .to_numpy(dtype="datetime64[ns]")
        .astype(np.int64)
    )
    latitudes = data["latitude"].to_numpy(dtype=float)
    longitudes = data["longitude"].to_numpy(dtype=float)

    modis_positions = np.flatnonzero(sources == "MODIS")
    viirs_positions = np.flatnonzero(sources == "VIIRS")
    viirs_positions = viirs_positions[
        np.argsort(times_ns[viirs_positions], kind="stable")
    ]
    viirs_times = times_ns[viirs_positions]
    window_ns = int(np.ceil(config.max_minutes * 60 * 1e9))
    candidates = []

    for modis_position in modis_positions:
        modis_time = times_ns[modis_position]
        start = np.searchsorted(viirs_times, modis_time - window_ns, side="left")
        end = np.searchsorted(viirs_times, modis_time + window_ns, side="right")
        nearby = viirs_positions[start:end]
        if not len(nearby):
            continue

        minutes = np.abs(modis_time - times_ns[nearby]) / 1e9 / 60
        distances = _distance_km(
            latitudes[modis_position],
            longitudes[modis_position],
            latitudes[nearby],
            longitudes[nearby],
        )
        keep = (minutes <= config.max_minutes) & (
            distances <= config.max_distance_km
        )
        candidates.extend(
            (float(distance), float(minute), int(modis_position), int(viirs_position))
            for distance, minute, viirs_position in zip(
                distances[keep], minutes[keep], nearby[keep]
            )
        )

    return candidates


def harmonize(
    data: pd.DataFrame, config: MatchConfig | None = None
) -> pd.DataFrame:
    """Classify records and pair the nearest compatible MODIS/VIIRS signals."""
    config = config or MatchConfig()
    validate_schema(data)
    result = data.copy()
    result["observed_at"] = pd.to_datetime(result["observed_at"], utc=True)
    records = list(result.to_dict("records"))
    candidates = _find_candidates(result, config)

    match_status = [
        "MODIS only" if row["source"] == "MODIS" else "VIIRS only"
        for row in records
    ]
    matched_id = [pd.NA] * len(records)
    match_distance_km = [float("nan")] * len(records)
    matched_modis = set()
    matched_viirs = set()

    for distance_km, _, modis_position, viirs_position in sorted(candidates):
        if modis_position in matched_modis or viirs_position in matched_viirs:
            continue

        modis_row = records[modis_position]
        viirs_row = records[viirs_position]
        match_status[modis_position] = "matched"
        match_status[viirs_position] = "matched"
        matched_id[modis_position] = viirs_row["id"]
        matched_id[viirs_position] = modis_row["id"]
        match_distance_km[modis_position] = distance_km
        match_distance_km[viirs_position] = distance_km
        matched_modis.add(modis_position)
        matched_viirs.add(viirs_position)

    result["match_status"] = match_status
    result["matched_id"] = matched_id
    result["match_distance_km"] = match_distance_km
    return result
