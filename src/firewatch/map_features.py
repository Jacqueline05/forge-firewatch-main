from __future__ import annotations

from math import asin, atan2, cos, degrees, radians, sin

import pandas as pd


EARTH_RADIUS_KM = 6371.0


def build_map_features(observations: pd.DataFrame) -> pd.DataFrame:
    """Represent each mutually matched pair as one map feature."""
    rows = list(observations.to_dict("records"))
    positions_by_id = {row["id"]: position for position, row in enumerate(rows)}
    included = set()
    features = []

    for position, row in enumerate(rows):
        if position in included:
            continue

        partner_position = positions_by_id.get(row.get("matched_id"))
        partner = (
            rows[partner_position] if partner_position is not None else None
        )
        is_pair = (
            row.get("match_status") == "matched"
            and partner is not None
            and partner.get("matched_id") == row["id"]
        )
        if is_pair:
            included.add(partner_position)
            row_region = row.get("region", "Borneo")
            partner_region = partner.get("region", "Borneo")
            latitudes = [row["latitude"], partner["latitude"]]
            longitudes = [row["longitude"], partner["longitude"]]
            observed_at = min(row["observed_at"], partner["observed_at"])
            feature = {
                "id": f'{row["id"]} + {partner["id"]}',
                "source": "MODIS + VIIRS",
                "observed_at": observed_at,
                "latitude": sum(latitudes) / 2,
                "longitude": sum(longitudes) / 2,
                "confidence": max(row["confidence"], partner["confidence"]),
                "region": row_region
                if row_region == partner_region
                else f"{row_region} / {partner_region}",
                "match_status": "matched",
                "matched_id": f'{row["id"]}, {partner["id"]}',
                "match_distance_km": row.get("match_distance_km"),
            }
        else:
            feature = {
                key: row.get(key)
                for key in (
                    "id",
                    "source",
                    "observed_at",
                    "latitude",
                    "longitude",
                    "confidence",
                    "region",
                    "match_status",
                    "matched_id",
                    "match_distance_km",
                )
            }

        included.add(position)
        feature["observation_date"] = feature[
            "observed_at"
        ].strftime("%Y-%m-%d")
        features.append(feature)

    return pd.DataFrame(features)


def coverage_circle(
    latitude: float, longitude: float, radius_km: float, points: int = 48
) -> tuple[list[float], list[float]]:
    """Return coordinates for a geodesic circle around a map feature."""
    angular_distance = radius_km / EARTH_RADIUS_KM
    lat1 = radians(latitude)
    lon1 = radians(longitude)
    latitudes = []
    longitudes = []

    for bearing_degrees in range(0, 360, 360 // points):
        bearing = radians(bearing_degrees)
        lat2 = asin(
            sin(lat1) * cos(angular_distance)
            + cos(lat1) * sin(angular_distance) * cos(bearing)
        )
        lon2 = lon1 + atan2(
            sin(bearing) * sin(angular_distance) * cos(lat1),
            cos(angular_distance) - sin(lat1) * sin(lat2),
        )
        latitudes.append(degrees(lat2))
        longitudes.append((degrees(lon2) + 540) % 360 - 180)

    latitudes.append(latitudes[0])
    longitudes.append(longitudes[0])
    return latitudes, longitudes
