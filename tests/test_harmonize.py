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


def _brute_force_pairs(records, config):
    """Reference: compare every MODIS record with every VIIRS record."""
    from math import cos, radians

    rows = records.assign(
        observed_at=pd.to_datetime(records["observed_at"], utc=True)
    ).to_dict("records")
    candidates = []
    for m, modis in enumerate(rows):
        for v, viirs in enumerate(rows):
            if modis["source"] != "MODIS" or viirs["source"] != "VIIRS":
                continue
            minutes = abs((modis["observed_at"] - viirs["observed_at"]).total_seconds()) / 60
            lat_km = (modis["latitude"] - viirs["latitude"]) * 111.0
            lon_km = (
                (modis["longitude"] - viirs["longitude"])
                * 111.0
                * cos(radians(modis["latitude"]))
            )
            distance = (lat_km**2 + lon_km**2) ** 0.5
            if minutes <= config.max_minutes and distance <= config.max_distance_km:
                candidates.append((distance, minutes, m, v))

    pairs, used_m, used_v = set(), set(), set()
    for _, _, m, v in sorted(candidates):
        if m not in used_m and v not in used_v:
            pairs.add((rows[m]["id"], rows[v]["id"]))
            used_m.add(m)
            used_v.add(v)
    return pairs


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_fast_matching_agrees_with_brute_force(seed):
    import numpy as np

    rng = np.random.default_rng(seed)
    count = 300
    records = pd.DataFrame(
        {
            "id": [f"R{i}" for i in range(count)],
            "source": rng.choice(["MODIS", "VIIRS"], count),
            "observed_at": pd.Timestamp("2026-09-01", tz="UTC")
            + pd.to_timedelta(rng.integers(0, 6 * 60, count), unit="min"),
            "latitude": rng.uniform(1.0, 1.5, count),
            "longitude": rng.uniform(110.0, 110.5, count),
            "confidence": 80,
        }
    )
    config = MatchConfig(max_minutes=30, max_distance_km=8.0)

    result = harmonize(records, config)
    matched = result[
        (result["source"] == "MODIS") & (result["match_status"] == "matched")
    ]
    fast_pairs = set(zip(matched["id"], matched["matched_id"]))

    assert fast_pairs == _brute_force_pairs(records, config)
    assert fast_pairs


def test_matching_handles_thousands_of_records_quickly():
    import time

    import numpy as np

    rng = np.random.default_rng(0)
    count = 6000
    records = pd.DataFrame(
        {
            "id": range(count),
            "source": ["MODIS", "VIIRS"] * (count // 2),
            "observed_at": pd.Timestamp("2026-09-01", tz="UTC")
            + pd.to_timedelta(rng.integers(0, 24 * 60, count), unit="min"),
            "latitude": rng.uniform(1, 3, count),
            "longitude": rng.uniform(110, 112, count),
            "confidence": 80,
        }
    )

    started = time.perf_counter()
    harmonize(records)
    assert time.perf_counter() - started < 10
