import io

import pandas as pd
import pytest

from src.firewatch.filters import filter_observations
from src.firewatch.loaders import load_observations, quality_score


def csv(text: str) -> io.StringIO:
    return io.StringIO(text.strip() + "\n")


def test_demo_data_loads_with_numeric_confidence():
    observations = load_observations("data/sample_hotspots.csv")

    assert len(observations) == 8
    assert pd.api.types.is_numeric_dtype(observations["confidence"])
    assert quality_score(observations) == 100


def test_firms_viirs_letter_confidence_becomes_numeric_and_filterable():
    observations = load_observations(
        csv(
            """
latitude,longitude,acq_date,acq_time,satellite,instrument,confidence
1.5,110.3,2026-09-01,152,N,VIIRS,h
1.6,110.4,2026-09-01,210,N,VIIRS,n
1.7,110.5,2026-09-01,615,N,VIIRS,l
"""
        )
    )

    assert list(observations["confidence"]) == [90, 60, 30]
    assert list(observations["source"]) == ["VIIRS"] * 3
    assert observations["observed_at"].iloc[0] == pd.Timestamp(
        "2026-09-01 01:52", tz="UTC"
    )

    filtered = filter_observations(
        observations,
        pd.Timestamp("2026-09-01").date(),
        pd.Timestamp("2026-09-01").date(),
        ["Borneo"],
        ["VIIRS"],
        50,
    )
    assert len(filtered) == 2


def test_firms_modis_satellite_codes_map_to_modis():
    observations = load_observations(
        csv(
            """
latitude,longitude,acq_date,acq_time,satellite,confidence
1.5,110.3,2026-09-01,0230,Terra,75
1.6,110.4,2026-09-01,0545,A,40
"""
        )
    )

    assert list(observations["source"]) == ["MODIS", "MODIS"]
    assert list(observations["confidence"]) == [75, 40]


def test_uppercase_column_names_are_accepted():
    observations = load_observations(
        csv(
            """
ID,Source,Observed_At,Latitude,Longitude,Confidence
M1,modis,2026-09-01T02:00:00Z,1.5,110.3,80
"""
        )
    )

    assert observations.iloc[0]["id"] == "M1"
    assert observations.iloc[0]["source"] == "MODIS"


def test_unknown_source_gives_readable_error():
    with pytest.raises(ValueError, match="MODIS or VIIRS"):
        load_observations(
            csv(
                """
id,source,observed_at,latitude,longitude,confidence
X1,LANDSAT,2026-09-01T02:00:00Z,1.5,110.3,80
"""
            )
        )


def test_missing_satellite_information_gives_readable_error():
    with pytest.raises(ValueError, match="Missing required fields: source"):
        load_observations(
            csv(
                """
latitude,longitude,acq_date,confidence
1.5,110.3,2026-09-01,80
"""
            )
        )
