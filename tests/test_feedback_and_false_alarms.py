import pandas as pd
import pytest

from src.firewatch.false_alarms import flag_false_alarms, load_known_sources
from src.firewatch.feedback import FeedbackStore, attach_feedback, false_alarm_sites


def observations():
    return pd.DataFrame(
        {
            "id": ["A", "B", "C"],
            "latitude": [3.0, 3.001, 2.0],
            "longitude": [113.0, 113.001, 111.0],
            "type": [0, 0, 2],
        }
    )


def test_firms_static_source_type_is_flagged():
    flagged = flag_false_alarms(observations(), load_known_sources("missing.csv"))

    assert flagged["false_alarm_reason"].tolist() == [
        "", "", "Other static land source (FIRMS)"
    ]


def test_known_heat_source_flags_nearby_detections(tmp_path):
    path = tmp_path / "known.csv"
    path.write_text(
        "# comment line\nname,latitude,longitude,radius_km,kind\n"
        "Test flare,3.0,113.0,0.5,Gas flare\n"
    )

    flagged = flag_false_alarms(observations(), load_known_sources(path))

    assert flagged["false_alarm_reason"].tolist()[:2] == [
        "Gas flare: Test flare", "Gas flare: Test flare"
    ]


def test_shipped_known_sources_file_is_valid():
    sources = load_known_sources("data/known_heat_sources.csv")

    assert list(sources.columns) == ["name", "latitude", "longitude", "radius_km", "kind"]


def test_reports_round_trip_and_attach_to_nearby_event(tmp_path):
    store = FeedbackStore(tmp_path / "reports.csv")
    store.add(2.8, 112.2, "2026-09-03", "confirmed_fire", "Seen by BOMBA", "team")
    store.add(4.4, 114.0, "2026-09-03", "not_sure")

    events = pd.DataFrame(
        {
            "latitude": [2.801, 1.5],
            "longitude": [112.201, 110.3],
            "first_seen": pd.to_datetime(["2026-09-01T05:00Z", "2026-09-01T05:00Z"]),
            "last_seen": pd.to_datetime(["2026-09-04T05:00Z", "2026-09-01T05:00Z"]),
        }
    )
    attached = attach_feedback(events, store.load())

    assert attached["ground_report"].tolist() == ["Confirmed fire", ""]
    assert attached["ground_note"].iloc[0] == "Seen by BOMBA"


def test_old_report_does_not_attach_to_a_new_fire(tmp_path):
    store = FeedbackStore(tmp_path / "reports.csv")
    store.add(2.8, 112.2, "2026-01-01", "confirmed_fire")
    events = pd.DataFrame(
        {
            "latitude": [2.8], "longitude": [112.2],
            "first_seen": pd.to_datetime(["2026-09-01T05:00Z"]),
            "last_seen": pd.to_datetime(["2026-09-02T05:00Z"]),
        }
    )

    assert attach_feedback(events, store.load())["ground_report"].iloc[0] == ""


def test_false_alarm_reports_become_known_sources(tmp_path):
    store = FeedbackStore(tmp_path / "reports.csv")
    store.add(3.0, 113.0, "2026-09-03", "false_alarm", "Factory chimney")
    store.add(2.0, 111.0, "2026-09-03", "confirmed_fire")

    sites = false_alarm_sites(store.load())
    flagged = flag_false_alarms(observations().drop(columns="type"), sites)

    assert sites["name"].tolist() == ["Factory chimney"]
    assert flagged["false_alarm_reason"].tolist() == [
        "Reported false alarm: Factory chimney",
        "Reported false alarm: Factory chimney",
        "",
    ]


def test_invalid_verdict_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        FeedbackStore(tmp_path / "r.csv").add(1, 1, "2026-09-01", "maybe")
