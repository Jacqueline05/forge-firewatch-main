"""Towns and small geography helpers used across Borneo FireWatch."""
from __future__ import annotations

import numpy as np
import pandas as pd


EARTH_RADIUS_KM = 6371.0
# Sarawak and the rest of Borneo use UTC+8 all year (no daylight saving).
LOCAL_UTC_OFFSET = pd.Timedelta(hours=8)

# Approximate town-centre coordinates, used to describe locations and to
# check which towns may be downwind of a fire.
TOWNS = pd.DataFrame(
    [
        ("Kuching", 1.5535, 110.3593),
        ("Sibu", 2.2870, 111.8305),
        ("Miri", 4.3995, 113.9914),
        ("Bintulu", 3.1667, 113.0333),
        ("Mukah", 2.8988, 112.0914),
        ("Sri Aman", 1.2370, 111.4621),
        ("Sarikei", 2.1271, 111.5218),
        ("Betong", 1.4100, 111.5300),
        ("Kapit", 2.0167, 112.9333),
        ("Limbang", 4.7500, 115.0000),
        ("Kota Kinabalu", 5.9804, 116.0735),
        ("Sandakan", 5.8402, 118.1179),
        ("Tawau", 4.2448, 117.8912),
        ("Bandar Seri Begawan", 4.9031, 114.9398),
        ("Pontianak", -0.0263, 109.3425),
        ("Palangka Raya", -2.2136, 113.9108),
        ("Banjarmasin", -3.3186, 114.5944),
        ("Samarinda", -0.5022, 117.1536),
        ("Balikpapan", -1.2379, 116.8529),
    ],
    columns=["town", "latitude", "longitude"],
)

COMPASS_EN = [
    "north", "north-east", "east", "south-east",
    "south", "south-west", "west", "north-west",
]
COMPASS_MS = [
    "utara", "timur laut", "timur", "tenggara",
    "selatan", "barat daya", "barat", "barat laut",
]


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km. Accepts scalars or numpy arrays."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def bearing_deg(lat1, lon1, lat2, lon2):
    """Initial compass bearing from point 1 to point 2 (0 = north)."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    x = np.sin(lon2 - lon1) * np.cos(lat2)
    y = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(lon2 - lon1)
    return (np.degrees(np.arctan2(x, y)) + 360) % 360


def destination(lat, lon, bearing, distance_km):
    """Point reached by travelling ``distance_km`` along ``bearing``."""
    angular = distance_km / EARTH_RADIUS_KM
    lat1, lon1, theta = np.radians(lat), np.radians(lon), np.radians(bearing)
    lat2 = np.arcsin(
        np.sin(lat1) * np.cos(angular) + np.cos(lat1) * np.sin(angular) * np.cos(theta)
    )
    lon2 = lon1 + np.arctan2(
        np.sin(theta) * np.sin(angular) * np.cos(lat1),
        np.cos(angular) - np.sin(lat1) * np.sin(lat2),
    )
    return float(np.degrees(lat2)), float((np.degrees(lon2) + 540) % 360 - 180)


def compass(bearing: float, language: str = "en") -> str:
    names = COMPASS_MS if language == "ms" else COMPASS_EN
    return names[int(((bearing % 360) + 22.5) // 45) % 8]


def nearest_town(lat: float, lon: float) -> tuple[str, float]:
    distances = haversine_km(
        lat, lon, TOWNS["latitude"].to_numpy(), TOWNS["longitude"].to_numpy()
    )
    index = int(np.argmin(distances))
    return str(TOWNS["town"].iloc[index]), float(distances[index])


def nearest_towns(latitudes, longitudes) -> list[str]:
    """Nearest town name for each point (vectorized)."""
    lat = np.asarray(latitudes, dtype=float)[:, None]
    lon = np.asarray(longitudes, dtype=float)[:, None]
    distances = haversine_km(
        lat, lon, TOWNS["latitude"].to_numpy()[None, :], TOWNS["longitude"].to_numpy()[None, :]
    )
    return TOWNS["town"].to_numpy()[np.argmin(distances, axis=1)].tolist()


def local_date(timestamps: pd.Series) -> pd.Series:
    """Calendar date in Sarawak time (UTC+8) for UTC timestamps."""
    return (timestamps + LOCAL_UTC_OFFSET).dt.date
