from __future__ import annotations

import pandas as pd

from .harmonize import REQUIRED_COLUMNS, validate_schema


MODIS_SATELLITES = {"MODIS", "TERRA", "AQUA", "T", "A"}
CONFIDENCE_LABELS = {
    "l": 30,
    "low": 30,
    "n": 60,
    "nominal": 60,
    "h": 90,
    "high": 90,
}


def _normalize_source(observations: pd.DataFrame) -> pd.Series | None:
    """Use an explicit source or FIRMS instrument column, else infer it."""
    for column in ("source", "instrument"):
        if column in observations:
            return observations[column].astype(str).str.strip().str.upper()
    if "satellite" in observations:
        return observations["satellite"].map(
            lambda value: "MODIS"
            if str(value).strip().upper() in MODIS_SATELLITES
            else "VIIRS"
        )
    return None


def _normalize_observed_at(observations: pd.DataFrame) -> pd.Series | None:
    if "observed_at" in observations:
        return pd.to_datetime(observations["observed_at"], errors="coerce", utc=True)
    if "acq_date" not in observations:
        return None

    if "acq_time" in observations:
        times = (
            pd.to_numeric(observations["acq_time"], errors="coerce")
            .fillna(0)
            .astype(int)
            .astype(str)
            .str.zfill(4)
        )
    else:
        times = pd.Series("0000", index=observations.index)

    return pd.to_datetime(
        observations["acq_date"].astype(str)
        + " "
        + times.str[:2]
        + ":"
        + times.str[2:]
        + ":00",
        errors="coerce",
        utc=True,
    )


def _normalize_confidence(observations: pd.DataFrame) -> pd.Series | None:
    """Convert confidence to a 0-100 score.

    MODIS reports a number; VIIRS reports low/nominal/high as l/n/h.
    """
    if "confidence" not in observations:
        return None

    raw = observations["confidence"]
    labels = raw.astype(str).str.strip().str.lower().map(CONFIDENCE_LABELS)
    return labels.fillna(pd.to_numeric(raw, errors="coerce"))


def load_observations(source) -> pd.DataFrame:
    """Load a CSV in the project schema or in NASA FIRMS format.

    ``source`` is a file path or a file-like object. Raises ValueError with a
    readable message when the data cannot be used.
    """
    observations = pd.read_csv(source)
    observations.columns = [str(column).strip().lower() for column in observations.columns]

    normalizers = {
        "source": _normalize_source,
        "observed_at": _normalize_observed_at,
        "confidence": _normalize_confidence,
    }
    for column, normalize in normalizers.items():
        values = normalize(observations)
        if values is not None:
            observations[column] = values
    for column in ("latitude", "longitude"):
        if column in observations:
            observations[column] = pd.to_numeric(observations[column], errors="coerce")
    if "region" not in observations:
        observations["region"] = "Borneo"
    if "id" not in observations:
        observations["id"] = [f"OBS-{i:04d}" for i in range(len(observations))]

    missing = sorted(REQUIRED_COLUMNS.difference(observations.columns))
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    observations = observations.dropna(subset=sorted(REQUIRED_COLUMNS)).copy()
    validate_schema(observations)
    return observations


def quality_score(observations: pd.DataFrame) -> int:
    checks = [
        observations["observed_at"].notna().all(),
        observations["latitude"].between(-90, 90).all(),
        observations["longitude"].between(-180, 180).all(),
        observations["source"].isin({"MODIS", "VIIRS"}).all(),
        observations["id"].is_unique,
    ]
    return round(sum(checks) / len(checks) * 100)
