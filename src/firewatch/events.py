"""Group individual satellite detections into multi-day fire events."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .places import bearing_deg, compass, haversine_km, local_date, nearest_town


@dataclass(frozen=True)
class EventConfig:
    # Detections closer than this (in km) can belong to the same event.
    link_distance_km: float = 2.0
    # ...as long as they are no more than this many days apart.
    max_gap_days: float = 2.0
    # Movement shorter than this is reported as "not spreading".
    min_spread_km: float = 0.5


EVENT_COLUMNS = [
    "event_id", "first_seen", "last_seen", "days_active", "detections",
    "modis_detections", "viirs_detections", "both_satellites", "latitude",
    "longitude", "max_confidence", "mean_confidence", "spread_km",
    "spread_bearing", "spread_direction", "nearest_town", "town_distance_km",
    "region", "on_peat",
]


def _find(parent: list[int], item: int) -> int:
    while parent[item] != item:
        parent[item] = parent[parent[item]]
        item = parent[item]
    return item


def _link_detections(data: pd.DataFrame, config: EventConfig) -> np.ndarray:
    """Return a group label per row (union-find over nearby detections)."""
    count = len(data)
    parent = list(range(count))
    latitudes = data["latitude"].to_numpy(dtype=float)
    longitudes = data["longitude"].to_numpy(dtype=float)
    times = data["observed_at"].astype("int64").to_numpy() / 1e9 / 86400

    # Grid cells at least link_distance wide so neighbours are always in
    # the same or an adjacent cell.
    lat_cell = config.link_distance_km / 111.0
    max_abs_lat = min(float(np.abs(latitudes).max()), 85.0)
    lon_cell = lat_cell / np.cos(np.radians(max_abs_lat))
    cells: dict[tuple[int, int], list[int]] = defaultdict(list)
    for index, (lat, lon) in enumerate(zip(latitudes, longitudes)):
        cells[(int(lat // lat_cell), int(lon // lon_cell))].append(index)

    for (row, col), members in cells.items():
        neighbours = [
            other
            for d_row in (-1, 0, 1)
            for d_col in (-1, 0, 1)
            for other in cells.get((row + d_row, col + d_col), [])
        ]
        neighbours = np.array(neighbours)
        for index in members:
            close = neighbours[
                (neighbours > index)
                & (np.abs(times[neighbours] - times[index]) <= config.max_gap_days)
            ]
            if not len(close):
                continue
            distances = haversine_km(
                latitudes[index], longitudes[index], latitudes[close], longitudes[close]
            )
            for other in close[distances <= config.link_distance_km]:
                root_a, root_b = _find(parent, index), _find(parent, int(other))
                if root_a != root_b:
                    parent[root_b] = root_a

    return np.array([_find(parent, index) for index in range(count)])


def build_events(
    observations: pd.DataFrame, config: EventConfig | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Group harmonized detections into fire events.

    Returns ``(events, observations_with_event_id)``. An event is a set of
    detections linked by being close in both place and time, so a fire
    that keeps burning over several days becomes one event.
    """
    config = config or EventConfig()
    data = observations.reset_index(drop=True).copy()
    if data.empty:
        data["event_id"] = pd.Series(dtype=str)
        return pd.DataFrame(columns=EVENT_COLUMNS), data
    if "on_peat" not in data:
        data["on_peat"] = False
    data["local_date"] = local_date(data["observed_at"])
    data["_group"] = _link_detections(data, config)

    events = []
    for _, group in data.groupby("_group", sort=False):
        days = sorted(group["local_date"].unique())
        first_day = group[group["local_date"] == days[0]]
        last_day = group[group["local_date"] == days[-1]]
        spread_km = float(
            haversine_km(
                first_day["latitude"].mean(), first_day["longitude"].mean(),
                last_day["latitude"].mean(), last_day["longitude"].mean(),
            )
        )
        spreading = len(days) > 1 and spread_km >= config.min_spread_km
        spread_bearing = (
            float(
                bearing_deg(
                    first_day["latitude"].mean(), first_day["longitude"].mean(),
                    last_day["latitude"].mean(), last_day["longitude"].mean(),
                )
            )
            if spreading
            else np.nan
        )
        latitude = float(group["latitude"].mean())
        longitude = float(group["longitude"].mean())
        town, town_km = nearest_town(latitude, longitude)
        regions = group["region"].astype(str).mode() if "region" in group else []
        events.append(
            {
                "_group": group["_group"].iloc[0],
                "first_seen": group["observed_at"].min(),
                "last_seen": group["observed_at"].max(),
                "days_active": len(days),
                "detections": len(group),
                "modis_detections": int((group["source"] == "MODIS").sum()),
                "viirs_detections": int((group["source"] == "VIIRS").sum()),
                "both_satellites": bool(
                    (group.get("match_status") == "matched").any()
                    if "match_status" in group
                    else False
                ),
                "latitude": latitude,
                "longitude": longitude,
                "max_confidence": float(group["confidence"].max()),
                "mean_confidence": float(group["confidence"].mean()),
                "spread_km": spread_km if spreading else 0.0,
                "spread_bearing": spread_bearing,
                "spread_direction": compass(spread_bearing) if spreading else "",
                "nearest_town": town,
                "town_distance_km": town_km,
                "region": regions.iloc[0] if len(regions) else "",
                "on_peat": bool(group["on_peat"].any()),
            }
        )

    events = pd.DataFrame(events).sort_values(
        ["first_seen", "latitude"], kind="stable"
    )
    events["event_id"] = [f"E{index:03d}" for index in range(1, len(events) + 1)]
    data["event_id"] = data["_group"].map(events.set_index("_group")["event_id"])
    events = events.drop(columns="_group").reset_index(drop=True)[EVENT_COLUMNS]
    return events, data.drop(columns=["_group"])
