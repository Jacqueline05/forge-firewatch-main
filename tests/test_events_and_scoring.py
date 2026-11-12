import json

import numpy as np
import pandas as pd
import pytest

from src.firewatch.events import EventConfig, build_events
from src.firewatch.harmonize import harmonize
from src.firewatch.peat import PeatLayer, load_peat_layer, points_on_peat
from src.firewatch.places import compass, local_date, nearest_town
from src.firewatch.scoring import score_events


def detection(id_, source, when, lat, lon, confidence=80):
    return {
        "id": id_, "source": source, "observed_at": when,
        "latitude": lat, "longitude": lon, "confidence": confidence,
        "region": "Test",
    }


def multi_day_fire():
    return pd.DataFrame(
        [
            detection("M1", "MODIS", "2026-09-01T05:30:00Z", 2.800, 112.200),
            detection("V1", "VIIRS", "2026-09-01T05:40:00Z", 2.8008, 112.2009),
            detection("V2", "VIIRS", "2026-09-02T05:40:00Z", 2.805, 112.205),
            detection("V3", "VIIRS", "2026-09-03T05:40:00Z", 2.810, 112.210),
            # A separate fire far away.
            detection("M9", "MODIS", "2026-09-03T03:00:00Z", 4.40, 114.00, 50),
        ]
    )


def test_detections_on_consecutive_days_form_one_event():
    events, observations = build_events(harmonize(multi_day_fire()))

    assert len(events) == 2
    fire = events.sort_values("detections").iloc[-1]
    assert fire["detections"] == 4
    assert fire["days_active"] == 3
    assert fire["both_satellites"]
    assert fire["spread_direction"] == "north-east"
    assert fire["nearest_town"] == "Mukah"
    assert observations.groupby("event_id").size().sort_values().tolist() == [1, 4]


def test_detections_too_far_apart_in_time_are_separate_events():
    records = multi_day_fire().iloc[:2].copy()
    records.loc[1, "observed_at"] = "2026-09-10T05:40:00Z"

    events, _ = build_events(harmonize(records), EventConfig(max_gap_days=2))

    assert len(events) == 2


def test_event_days_use_sarawak_time():
    # 20:00 UTC on 1 Sept is 04:00 on 2 Sept in Sarawak.
    times = pd.to_datetime(pd.Series(["2026-09-01T20:00:00Z"]), utc=True)
    assert str(local_date(times).iloc[0]) == "2026-09-02"


def test_empty_input_gives_empty_events():
    empty = harmonize(multi_day_fire().iloc[0:0])
    events, observations = build_events(empty)

    assert events.empty and "event_id" in observations


def test_attention_score_rewards_agreement_persistence_and_peat():
    events, _ = build_events(harmonize(multi_day_fire()))
    events["on_peat"] = events["nearest_town"] == "Mukah"

    scored = score_events(events, peat_available=True)

    top = scored.iloc[0]
    assert top["nearest_town"] == "Mukah"
    assert top["attention_level"] == "High"
    assert "on peatland" in top["reasons"]
    assert "atas tanah gambut" in top["reasons_ms"]
    assert scored.iloc[-1]["attention_level"] == "Low"


def test_score_without_peat_layer_still_reaches_100():
    events = pd.DataFrame(
        {
            "both_satellites": [True], "days_active": [5], "on_peat": [False],
            "mean_confidence": [100.0], "last_seen": [pd.Timestamp("2026-09-01")],
        }
    )

    assert score_events(events, peat_available=False)["attention_score"].iloc[0] == 100
    assert score_events(events, peat_available=True)["attention_score"].iloc[0] == 75


def test_points_on_peat_handles_holes(tmp_path):
    square = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    hole = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]
    path = tmp_path / "peat.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "geometry": {
                        "type": "MultiPolygon", "coordinates": [[square, hole]]}}
                ],
            }
        )
    )
    layer = load_peat_layer(path)

    inside = points_on_peat([1, 5, 20], [1, 5, 20], layer)

    assert layer.available
    assert inside.tolist() == [True, False, False]


def test_missing_peat_file_means_layer_not_available(tmp_path):
    layer = load_peat_layer(tmp_path / "missing.geojson")

    assert not layer.available
    assert not points_on_peat([1.0], [1.0], PeatLayer()).any()


def test_demo_peat_layer_covers_demo_mukah_fire():
    layer = load_peat_layer("data/demo_peat_illustrative.geojson", illustrative=True)

    assert points_on_peat([2.80], [112.20], layer).tolist() == [True]
    assert points_on_peat([1.55], [110.36], layer).tolist() == [False]


@pytest.mark.parametrize(
    "bearing,english,malay",
    [(0, "north", "utara"), (44, "north-east", "timur laut"), (225, "south-west", "barat daya")],
)
def test_compass_names(bearing, english, malay):
    assert compass(bearing) == english
    assert compass(bearing, "ms") == malay


def test_nearest_town():
    town, distance = nearest_town(1.56, 110.36)

    assert town == "Kuching"
    assert distance < 2
    assert np.isfinite(distance)
