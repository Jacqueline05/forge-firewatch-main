from datetime import date

import pandas as pd

from src.firewatch.filters import filter_observations


def test_filter_observations_applies_inclusive_dates_and_other_filters():
    observations = pd.DataFrame(
        [
            {
                "id": "M1",
                "observed_at": "2026-09-01T02:00:00Z",
                "region": "Kuching",
                "source": "MODIS",
                "confidence": 80,
            },
            {
                "id": "V1",
                "observed_at": "2026-09-02T02:00:00Z",
                "region": "Miri",
                "source": "VIIRS",
                "confidence": 90,
            },
            {
                "id": "M2",
                "observed_at": "2026-09-02T03:00:00Z",
                "region": "Kuching",
                "source": "MODIS",
                "confidence": 50,
            },
            {
                "id": "M3",
                "observed_at": "2026-09-03T02:00:00Z",
                "region": "Kuching",
                "source": "MODIS",
                "confidence": 80,
            },
        ]
    )
    observations["observed_at"] = pd.to_datetime(
        observations["observed_at"], utc=True
    )

    result = filter_observations(
        observations,
        date(2026, 9, 1),
        date(2026, 9, 2),
        ["Kuching", "Miri"],
        ["MODIS", "VIIRS"],
        70,
    )

    assert set(result["id"]) == {"M1", "V1"}


def test_filter_observations_with_no_regions_returns_no_records():
    observations = pd.DataFrame(
        {
            "observed_at": pd.to_datetime(["2026-09-01T02:00:00Z"]),
            "region": ["Kuching"],
            "source": ["MODIS"],
            "confidence": [80],
        }
    )

    result = filter_observations(
        observations,
        date(2026, 9, 1),
        date(2026, 9, 1),
        [],
        ["MODIS"],
        0,
    )

    assert result.empty
