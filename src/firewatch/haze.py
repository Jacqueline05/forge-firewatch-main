"""Rough smoke-direction outlook: which towns are downwind of active fires.

This is a simple screening estimate (straight-line drift with the average
10 m wind), not an air-quality or dispersion forecast.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import pandas as pd

from .places import TOWNS, bearing_deg, destination, haversine_km


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
# Only towns inside this angle either side of the downwind direction count.
CONE_HALF_ANGLE_DEG = 30
# Smoke drift is capped; beyond this a straight-line estimate means little.
MAX_DRIFT_KM = 300
MIN_WIND_KMH = 2.0
# Towns this close to a fire are listed whatever the wind direction.
NEARBY_KM = 15

Fetcher = Callable[[str], str]


class WeatherError(RuntimeError):
    """The wind forecast could not be fetched."""


@dataclass(frozen=True)
class Wind:
    speed_kmh: float
    # Direction the wind blows TOWARDS (smoke drift), 0 = north.
    toward_deg: float


def _http_get(url: str) -> str:
    try:
        with urlopen(url, timeout=30) as response:
            return response.read().decode("utf-8")
    except URLError as error:
        raise WeatherError(f"Could not reach Open-Meteo: {error.reason}") from error


def average_wind(speeds_kmh, directions_from_deg) -> Wind:
    """Vector-average hourly winds (meteorological "from" directions)."""
    speeds = np.asarray(speeds_kmh, dtype=float)
    toward = np.radians((np.asarray(directions_from_deg, dtype=float) + 180) % 360)
    valid = ~(np.isnan(speeds) | np.isnan(toward))
    if not valid.any():
        return Wind(0.0, 0.0)
    east = np.mean(speeds[valid] * np.sin(toward[valid]))
    north = np.mean(speeds[valid] * np.cos(toward[valid]))
    return Wind(
        speed_kmh=float(np.hypot(east, north)),
        toward_deg=float((np.degrees(np.arctan2(east, north)) + 360) % 360),
    )


def fetch_winds(
    points: list[tuple[float, float]], hours: int = 24, fetch: Fetcher = _http_get
) -> list[Wind]:
    """Average forecast wind over the next ``hours`` at each (lat, lon)."""
    if not points:
        return []
    query = urlencode(
        {
            "latitude": ",".join(f"{lat:.4f}" for lat, _ in points),
            "longitude": ",".join(f"{lon:.4f}" for _, lon in points),
            "hourly": "wind_speed_10m,wind_direction_10m",
            "wind_speed_unit": "kmh",
            "forecast_days": 2,
            "timezone": "GMT",
        }
    )
    payload = json.loads(fetch(f"{OPEN_METEO_URL}?{query}"))
    locations = payload if isinstance(payload, list) else [payload]
    if len(locations) != len(points):
        raise WeatherError("Open-Meteo returned an unexpected response")

    now = pd.Timestamp.now(tz="UTC").floor("h").tz_localize(None)
    winds = []
    for location in locations:
        hourly = location["hourly"]
        times = pd.to_datetime(hourly["time"])
        start = int(np.searchsorted(times, now))
        window = slice(start, start + hours)
        winds.append(
            average_wind(
                hourly["wind_speed_10m"][window], hourly["wind_direction_10m"][window]
            )
        )
    return winds


def haze_outlook(
    events: pd.DataFrame, winds: list[Wind], hours: int = 24
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return ``(towns_at_risk, plumes)`` for events with a known wind.

    ``towns_at_risk`` has one row per event/town pair; ``plumes`` has the
    drift line (start and end point) for each event to draw on the map.
    """
    town_lat = TOWNS["latitude"].to_numpy()
    town_lon = TOWNS["longitude"].to_numpy()
    at_risk, plumes = [], []

    for (_, event), wind in zip(events.iterrows(), winds):
        if wind.speed_kmh < MIN_WIND_KMH:
            continue
        drift_km = min(wind.speed_kmh * hours, MAX_DRIFT_KM)
        end_lat, end_lon = destination(
            event["latitude"], event["longitude"], wind.toward_deg, drift_km
        )
        plumes.append(
            {
                "event_id": event["event_id"],
                "latitude": event["latitude"],
                "longitude": event["longitude"],
                "end_latitude": end_lat,
                "end_longitude": end_lon,
                "wind_kmh": wind.speed_kmh,
                "toward_deg": wind.toward_deg,
            }
        )
        distances = haversine_km(event["latitude"], event["longitude"], town_lat, town_lon)
        bearings = bearing_deg(event["latitude"], event["longitude"], town_lat, town_lon)
        off_axis = np.abs((bearings - wind.toward_deg + 180) % 360 - 180)
        hits = (distances <= NEARBY_KM) | (
            (distances <= drift_km) & (off_axis <= CONE_HALF_ANGLE_DEG)
        )
        for index in np.flatnonzero(hits):
            at_risk.append(
                {
                    "event_id": event["event_id"],
                    "town": TOWNS["town"].iloc[index],
                    "distance_km": float(distances[index]),
                    "hours_away": float(distances[index] / wind.speed_kmh),
                    "attention_level": event.get("attention_level", ""),
                }
            )

    towns = pd.DataFrame(
        at_risk,
        columns=["event_id", "town", "distance_km", "hours_away", "attention_level"],
    ).sort_values("hours_away", kind="stable")
    return towns.reset_index(drop=True), pd.DataFrame(plumes)
