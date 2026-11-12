"""Fetch hotspot data from the NASA FIRMS area API.

Get a free MAP_KEY at https://firms.modaps.eosdis.nasa.gov/api/map_key/
"""
from __future__ import annotations

import io
from datetime import date, timedelta
from typing import Callable
from urllib.error import URLError
from urllib.request import urlopen

import pandas as pd

from .loaders import load_observations
from .places import nearest_towns


FIRMS_AREA_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
# Near-real-time products (last few weeks).
LIVE_SOURCES = {
    "MODIS_NRT": "MODIS",
    "VIIRS_SNPP_NRT": "VIIRS S-NPP",
    "VIIRS_NOAA20_NRT": "VIIRS NOAA-20",
    "VIIRS_NOAA21_NRT": "VIIRS NOAA-21",
}
# west, south, east, north
AREAS = {
    "Sarawak": (109.5, 0.8, 115.8, 5.1),
    "Borneo": (108.5, -4.5, 119.5, 7.5),
}
MAX_DAY_RANGE = 10

Fetcher = Callable[[str], str]


class FirmsError(RuntimeError):
    """FIRMS could not be reached or rejected the request."""


def _http_get(url: str) -> str:
    try:
        with urlopen(url, timeout=60) as response:
            return response.read().decode("utf-8")
    except URLError as error:
        raise FirmsError(f"Could not reach NASA FIRMS: {error.reason}") from error


def area_url(
    map_key: str, source: str, bbox: tuple, day_range: int, start: date | None = None
) -> str:
    if not 1 <= day_range <= MAX_DAY_RANGE:
        raise ValueError(f"day_range must be between 1 and {MAX_DAY_RANGE}")
    area = ",".join(f"{value:g}" for value in bbox)
    url = f"{FIRMS_AREA_URL}/{map_key}/{source}/{area}/{day_range}"
    return f"{url}/{start.isoformat()}" if start else url


def fetch_area_csv(
    map_key: str,
    source: str,
    bbox: tuple,
    day_range: int,
    start: date | None = None,
    fetch: Fetcher = _http_get,
) -> pd.DataFrame:
    """Return the raw FIRMS rows for one product, area and date window."""
    text = fetch(area_url(map_key, source, bbox, day_range, start))
    if not text.lstrip().lower().startswith("latitude"):
        message = text.strip().splitlines()[0] if text.strip() else "empty response"
        raise FirmsError(f"NASA FIRMS rejected the request ({source}): {message}")
    return pd.read_csv(io.StringIO(text))


def fetch_live_observations(
    map_key: str,
    area: str = "Sarawak",
    day_range: int = 3,
    fetch: Fetcher = _http_get,
) -> pd.DataFrame:
    """Download the latest MODIS and VIIRS detections for an area.

    Returns rows in the project schema, with unique ids per product.
    """
    frames = []
    for source in LIVE_SOURCES:
        raw = fetch_area_csv(map_key, source, AREAS[area], day_range, fetch=fetch)
        if raw.empty:
            continue
        buffer = io.StringIO()
        raw.to_csv(buffer, index=False)
        buffer.seek(0)
        observations = load_observations(buffer)
        observations["id"] = [
            f"{source}-{index:05d}" for index in range(len(observations))
        ]
        observations["product"] = source
        observations["region"] = nearest_towns(
            observations["latitude"], observations["longitude"]
        )
        frames.append(observations)
    if not frames:
        return pd.DataFrame(
            columns=["id", "source", "observed_at", "latitude", "longitude",
                     "confidence", "region"]
        ).astype({"observed_at": "datetime64[ns, UTC]", "confidence": float,
                  "latitude": float, "longitude": float})
    return pd.concat(frames, ignore_index=True)


def _same_day(day: date, year: int) -> date:
    try:
        return day.replace(year=year)
    except ValueError:  # 29 February in a non-leap year
        return day.replace(year=year, day=28)


def history_counts(
    map_key: str,
    area: str,
    end: date,
    years: int = 11,
    day_range: int = MAX_DAY_RANGE,
    fetch: Fetcher = _http_get,
) -> pd.DataFrame:
    """Count MODIS detections in the same calendar window for past years.

    MODIS is used because it has a consistent record since 2000, so years
    can be compared fairly. Past years use the quality-checked archive
    (MODIS_SP); the current window uses near-real-time data (MODIS_NRT).
    """
    rows = []
    for offset in range(years - 1, -1, -1):
        year_end = _same_day(end, end.year - offset)
        start = year_end - timedelta(days=day_range - 1)
        products = ["MODIS_NRT"] if offset == 0 else ["MODIS_SP", "MODIS_NRT"]
        count = 0
        for product in products:
            count = len(
                fetch_area_csv(map_key, product, AREAS[area], day_range, start, fetch)
            )
            if count:
                break
        rows.append(
            {
                "year": year_end.year,
                "window": f"{start:%d %b} - {year_end:%d %b}",
                "detections": count,
                "current": offset == 0,
            }
        )
    return pd.DataFrame(rows)
