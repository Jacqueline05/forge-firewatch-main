import pandas as pd
import pytest

from src.firewatch.harmonize import MatchConfig, harmonize, validate_schema


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


def test_invalid_schema_is_rejected():
    invalid = pd.DataFrame({"id": ["M1"], "source": ["UNKNOWN"]})

    with pytest.raises(ValueError, match="Missing required columns"):
        validate_schema(invalid)
