import pandas as pd
import pytest

from src.firewatch.harmonize import MatchConfig, harmonize, validate_schema
from src.firewatch.auth import authenticate


def make_records():
    return pd.DataFrame(
        [
            {
                "id": "M1",
                "source": "MODIS",
                "observed_at": "2026-09-01T02:00:00Z",
                "latitude": 1.5,
                "longitude": 110.3,
                "confidence": 80,
            },
            {
                "id": "V1",
                "source": "VIIRS",
                "observed_at": "2026-09-01T02:15:00Z",
                "latitude": 1.51,
                "longitude": 110.31,
                "confidence": 90,
            },
            {
                "id": "M2",
                "source": "MODIS",
                "observed_at": "2026-09-01T10:00:00Z",
                "latitude": 2.0,
                "longitude": 111.0,
                "confidence": 50,
            },
        ]
    )


def test_records_within_time_and_distance_are_matched():
    result = harmonize(make_records())

    assert result.set_index("id").loc["M1", "match_status"] == "matched"
    assert result.set_index("id").loc["M1", "matched_id"] == "V1"
    assert result.set_index("id").loc["M2", "match_status"] == "MODIS only"


def test_time_window_can_exclude_a_candidate():
    result = harmonize(make_records(), MatchConfig(max_minutes=5))

    assert set(result["match_status"]) == {"MODIS only", "VIIRS only"}


def test_each_signal_matches_only_its_nearest_compatible_counterpart():
    records = pd.DataFrame(
        [
            {
                "id": "M1",
                "source": "MODIS",
                "observed_at": "2026-09-01T02:00:00Z",
                "latitude": 1.5,
                "longitude": 110.3,
                "confidence": 80,
            },
            {
                "id": "V1",
                "source": "VIIRS",
                "observed_at": "2026-09-01T02:15:00Z",
                "latitude": 1.51,
                "longitude": 110.31,
                "confidence": 90,
            },
            {
                "id": "V2",
                "source": "VIIRS",
                "observed_at": "2026-09-01T02:10:00Z",
                "latitude": 1.5001,
                "longitude": 110.3001,
                "confidence": 75,
            },
        ]
    )

    result = harmonize(records).set_index("id")

    assert result.loc["M1", "matched_id"] == "V2"
    assert result.loc["V2", "match_status"] == "matched"
    assert result.loc["V1", "match_status"] == "VIIRS only"
    assert result.loc["M1", "match_distance_km"] < 0.1
    assert result.loc["M1", "match_distance_km"] == result.loc[
        "V2", "match_distance_km"
    ]


def test_invalid_schema_is_rejected():
    invalid = pd.DataFrame({"id": ["M1"], "source": ["UNKNOWN"]})

    with pytest.raises(ValueError, match="Missing required columns"):
        validate_schema(invalid)


def test_authenticate_accepts_matching_credentials():
    assert authenticate("team", "secret", "team", "secret")


def test_authenticate_rejects_invalid_credentials():
    assert not authenticate("team", "wrong", "team", "secret")


def test_map_features_combine_matched_pair_at_midpoint():
    from src.firewatch.map_features import build_map_features

    features = build_map_features(harmonize(make_records()))
    pair = features[features["source"] == "MODIS + VIIRS"].iloc[0]

    assert pair["id"] == "M1 + V1"
    assert pair["matched_id"] == "M1, V1"
    assert pair["latitude"] == pytest.approx((1.5 + 1.51) / 2)
    assert pair["longitude"] == pytest.approx((110.3 + 110.31) / 2)
    assert pair["match_distance_km"] > 0
    assert len(features) == 2


def test_coverage_circle_uses_selected_distance_as_radius():
    from math import asin, cos, radians, sin, sqrt

    from src.firewatch.map_features import coverage_circle

    center_lat, center_lon, radius_km = 1.5, 110.3, 5.0
    latitudes, longitudes = coverage_circle(
        center_lat, center_lon, radius_km
    )
    lat1, lat2 = radians(center_lat), radians(latitudes[0])
    delta_lat = lat2 - lat1
    delta_lon = radians(longitudes[0] - center_lon)
    distance_km = 6371 * 2 * asin(
        sqrt(
            sin(delta_lat / 2) ** 2
            + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
        )
    )

    assert distance_km == pytest.approx(radius_km, abs=0.01)
    assert latitudes[0] == latitudes[-1]
    assert longitudes[0] == longitudes[-1]
