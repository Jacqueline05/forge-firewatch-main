"""Settlement labels and small geography helpers."""
from __future__ import annotations

import numpy as np
import pandas as pd


EARTH_RADIUS_KM = 6371.0
# UTC provides a consistent display date for detections anywhere in the world.
DISPLAY_UTC_OFFSET = pd.Timedelta(0)

# Representative global city coordinates for labels and smoke screening.
# Every detection is labeled with its nearest town from this list; the
# distance is shown alongside so far-away matches stay clear.
TOWNS = pd.DataFrame(
    [
        ("Vancouver", 49.2827, -123.1207),
        ("Los Angeles", 34.0522, -118.2437),
        ("Houston", 29.7604, -95.3698),
        ("Chicago", 41.8781, -87.6298),
        ("New York", 40.7128, -74.0060),
        ("Miami", 25.7617, -80.1918),
        ("Mexico City", 19.4326, -99.1332),
        ("Bogota", 4.7110, -74.0721),
        ("Manaus", -3.1190, -60.0217),
        ("Codajas", -3.8370, -62.0570),
        ("Lima", -12.0464, -77.0428),
        ("Sao Paulo", -23.5505, -46.6333),
        ("Buenos Aires", -34.6037, -58.3816),
        ("London", 51.5072, -0.1276),
        ("Madrid", 40.4168, -3.7038),
        ("Paris", 48.8566, 2.3522),
        ("Athens", 37.9838, 23.7275),
        ("Dakar", 14.7167, -17.4677),
        ("Lagos", 6.5244, 3.3792),
        ("Kinshasa", -4.4419, 15.2663),
        ("Kisangani", 0.5157, 25.1909),
        ("Nairobi", -1.2921, 36.8219),
        ("Johannesburg", -26.2041, 28.0473),
        ("Cairo", 30.0444, 31.2357),
        ("Istanbul", 41.0082, 28.9784),
        ("Riyadh", 24.7136, 46.6753),
        ("Dubai", 25.2048, 55.2708),
        ("Karachi", 24.8607, 67.0011),
        ("Mumbai", 19.0760, 72.8777),
        ("Delhi", 28.6139, 77.2090),
        ("Bhopal", 23.2599, 77.4126),
        ("Dhaka", 23.8103, 90.4125),
        ("Bangkok", 13.7563, 100.5018),
        ("Hanoi", 21.0285, 105.8542),
        ("Manila", 14.5995, 120.9842),
        ("Jakarta", -6.2088, 106.8456),
        ("Singapore", 1.3521, 103.8198),
        ("Beijing", 39.9042, 116.4074),
        ("Seoul", 37.5665, 126.9780),
        ("Tokyo", 35.6762, 139.6503),
        ("Perth", -31.9505, 115.8605),
        ("Darwin", -12.4634, 130.8456),
        ("Katherine", -14.4652, 132.2635),
        ("Sydney", -33.8688, 151.2093),
        ("Melbourne", -37.8136, 144.9631),
        ("Auckland", -36.8509, 174.7645),
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
    nearest = np.argmin(distances, axis=1)
    return TOWNS["town"].to_numpy()[nearest].tolist()


def local_date(timestamps: pd.Series) -> pd.Series:
    """Calendar date in UTC for timestamps."""
    return (timestamps + DISPLAY_UTC_OFFSET).dt.date
