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
    """Classify MODIS and VIIRS records by potential observation matches."""
    config = config or MatchConfig()
    validate_schema(data)
    result = data.copy()
    result["observed_at"] = pd.to_datetime(result["observed_at"], utc=True)
    result["match_status"] = "unmatched"
    result["matched_id"] = pd.NA

    modis = result[result["source"] == "MODIS"]
    viirs = result[result["source"] == "VIIRS"]
    for modis_index, modis_row in modis.iterrows():
        for viirs_index, viirs_row in viirs.iterrows():
            minutes = abs(
                (
                    modis_row["observed_at"] - viirs_row["observed_at"]
                ).total_seconds()
            ) / 60
            if minutes > config.max_minutes:
                continue
            if _distance_km(modis_row, viirs_row) > config.max_distance_km:
                continue
            result.loc[
                modis_index, ["match_status", "matched_id"]
            ] = ["matched", viirs_row["id"]]
            result.loc[viirs_index, ["match_status", "matched_id"]] = [
                "matched",
                modis_row["id"],
            ]

    result.loc[
        (result["source"] == "MODIS") & (result["match_status"] != "matched"),
        "match_status",
    ] = "MODIS only"
    result.loc[
        (result["source"] == "VIIRS") & (result["match_status"] != "matched"),
        "match_status",
    ] = "VIIRS only"
    return result
