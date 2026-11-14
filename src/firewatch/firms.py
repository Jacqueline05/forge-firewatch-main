"""Fetch hotspot data from the NASA FIRMS area API.

Get a free MAP_KEY at https://firms.modaps.eosdis.nasa.gov/api/map_key/
"""
from __future__ import annotations

import io
import math
from datetime import date
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
WORLD_AREA = "Worldwide"
_WORLD_NAMES = {"world", "worldwide"}
CUSTOM_AREA = "Custom bounding box"
MAX_DAY_RANGE = 5

Fetcher = Callable[[str], str]
BBox = tuple[float, float, float, float]


class FirmsError(RuntimeError):
    """FIRMS could not be reached or rejected the request."""


def _http_get(url: str) -> str:
    try:
        with urlopen(url, timeout=60) as response:
            return response.read().decode("utf-8")
    except URLError as error:
        raise FirmsError(f"Could not reach NASA FIRMS: {error.reason}") from error


def area_url(
    map_key: str, source: str, area: BBox | str, day_range: int,
    start: date | None = None
) -> str:
    if not 1 <= day_range <= MAX_DAY_RANGE:
        raise ValueError(f"day_range must be between 1 and {MAX_DAY_RANGE}")
    if isinstance(area, str):
        if area.lower() not in _WORLD_NAMES:
            raise ValueError("Area name must be 'worldwide' or a coordinate bounding box")
        area_path = "world"
    else:
        if len(area) != 4 or not all(math.isfinite(value) for value in area):
            raise ValueError(
                "bbox must contain four finite values: west, south, east, north"
            )
        west, south, east, north = area
        if not -180 <= west < east <= 180:
            raise ValueError("bbox longitudes must satisfy -180 <= west < east <= 180")
        if not -90 <= south < north <= 90:
            raise ValueError("bbox latitudes must satisfy -90 <= south < north <= 90")
        area_path = ",".join(f"{value:g}" for value in area)
    url = f"{FIRMS_AREA_URL}/{map_key}/{source}/{area_path}/{day_range}"
    return f"{url}/{start.isoformat()}" if start else url


def fetch_area_csv(
    map_key: str,
    source: str,
    area: BBox | str,
    day_range: int,
    start: date | None = None,
    fetch: Fetcher = _http_get,
) -> pd.DataFrame:
    """Return the raw FIRMS rows for one product, area and date window."""
    text = fetch(area_url(map_key, source, area, day_range, start))
    if not text.lstrip().lower().startswith("latitude"):
        message = text.strip().splitlines()[0] if text.strip() else "empty response"
        raise FirmsError(f"NASA FIRMS rejected the request ({source}): {message}")
    return pd.read_csv(io.StringIO(text))


def fetch_live_observations(
    map_key: str,
    area: str | BBox = WORLD_AREA,
    day_range: int = 1,
    fetch: Fetcher = _http_get,
) -> pd.DataFrame:
    """Download the latest MODIS and VIIRS detections for an area.

    Returns rows in the project schema, with unique ids per product.
    """
    if isinstance(area, str):
        if area.lower() in _WORLD_NAMES:
            firms_area = "world"
        else:
            try:
                firms_area = AREAS[area]
            except KeyError as error:
                raise ValueError(f"Unknown FIRMS area preset: {area}") from error
    else:
        firms_area = area

    frames = []
    for source in LIVE_SOURCES:
        raw = fetch_area_csv(map_key, source, firms_area, day_range, fetch=fetch)
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
