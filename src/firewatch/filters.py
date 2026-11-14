from datetime import date

import pandas as pd


def filter_bbox(
    observations: pd.DataFrame, bbox: tuple[float, float, float, float]
) -> pd.DataFrame:
    west, south, east, north = bbox
    in_bbox = (
        observations["longitude"].between(west, east)
        & observations["latitude"].between(south, north)
    )
    return observations[in_bbox].copy()


def filter_observations(
    observations: pd.DataFrame,
    start_date: date,
    end_date: date,
    regions: list[str],
    sources: list[str],
    min_confidence: int,
) -> pd.DataFrame:
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")

    date_mask = observations["observed_at"].dt.date.between(
        start_date, end_date
    )
    region_mask = observations["region"].astype(str).isin(regions)
    return observations[
        date_mask
        & region_mask
        & observations["source"].isin(sources)
        & (observations["confidence"] >= min_confidence)
    ].copy()
