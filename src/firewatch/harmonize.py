from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians

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


def _distance_km(first: pd.Series, second: pd.Series) -> float:
    """Approximate distance for the small regional distances in this MVP."""
    latitude_km = (first["latitude"] - second["latitude"]) * 111.0
    longitude_km = (
        (first["longitude"] - second["longitude"])
        * 111.0
        * cos(radians(first["latitude"]))
    )
    return float((latitude_km**2 + longitude_km**2) ** 0.5)


def harmonize(
    data: pd.DataFrame, config: MatchConfig | None = None
) -> pd.DataFrame:
    """Classify records and pair the nearest compatible MODIS/VIIRS signals."""
    config = config or MatchConfig()
    validate_schema(data)
    result = data.copy()
    result["observed_at"] = pd.to_datetime(result["observed_at"], utc=True)
    records = list(result.to_dict("records"))
    candidates = []

    for modis_position, modis_row in enumerate(records):
        if modis_row["source"] != "MODIS":
            continue
        for viirs_position, viirs_row in enumerate(records):
            if viirs_row["source"] != "VIIRS":
                continue
            minutes = abs(
                (
                    modis_row["observed_at"] - viirs_row["observed_at"]
                ).total_seconds()
            ) / 60
            distance_km = _distance_km(
                pd.Series(modis_row), pd.Series(viirs_row)
            )
            if (
                minutes <= config.max_minutes
                and distance_km <= config.max_distance_km
            ):
                candidates.append(
                    (
                        distance_km,
                        minutes,
                        modis_position,
                        viirs_position,
                    )
                )

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
