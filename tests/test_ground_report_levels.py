import pandas as pd

from src.firewatch.feedback import (
    CONFIRMS_TO_RAISE,
    FALSE_ALARMS_TO_LOWER,
    FeedbackStore,
    apply_ground_reports,
    attach_feedback,
    false_alarm_sites,
)


def scored_events(level="Medium", score=55):
    return pd.DataFrame(
        {
            "latitude": [2.8],
            "longitude": [112.2],
            "first_seen": pd.to_datetime(["2026-09-01T05:00Z"]),
            "last_seen": pd.to_datetime(["2026-09-03T05:00Z"]),
            "attention_score": [score],
            "attention_level": [level],
            "reasons": ["seen by both satellites"],
            "reasons_ms": ["dikesan kedua-dua satelit"],
        }
    )


def with_reports(tmp_path, verdicts, level="Medium"):
    store = FeedbackStore(tmp_path / "reports.csv")
    for verdict in verdicts:
        store.add(2.8, 112.2, "2026-09-03", verdict)
    return apply_ground_reports(attach_feedback(scored_events(level), store.load()))


def test_thresholds_need_more_agreement_to_lower_than_to_raise():
    assert CONFIRMS_TO_RAISE == 2
    assert FALSE_ALARMS_TO_LOWER == 3


def test_one_confirmation_is_not_enough(tmp_path):
    event = with_reports(tmp_path, ["confirmed_fire"]).iloc[0]

    assert event["attention_level"] == "Medium"
    assert event["level_change"] == ""
    assert event["confirmed_reports"] == 1


def test_two_confirmations_raise_medium_to_high(tmp_path):
    event = with_reports(tmp_path, ["confirmed_fire", "confirmed_fire"]).iloc[0]

    assert event["attention_level"] == "High"
    assert event["satellite_level"] == "Medium"
    assert event["level_change"] == "raised"
    assert event["attention_score"] == 55  # satellite score is unchanged
    assert "raised by 2 confirmed-fire reports" in event["reasons"]
    assert "dinaikkan" in event["reasons_ms"]


def test_two_false_alarms_are_not_enough_but_three_lower_high(tmp_path):
    two = with_reports(tmp_path / "a", ["false_alarm"] * 2, level="High").iloc[0]
    three = with_reports(tmp_path / "b", ["false_alarm"] * 3, level="High").iloc[0]

    assert two["attention_level"] == "High"
    assert three["attention_level"] == "Medium"
    assert three["level_change"] == "lowered"
    assert "lowered by 3 false-alarm reports" in three["reasons"]


def test_reports_cancel_out_and_not_sure_counts_as_neither(tmp_path):
    verdicts = ["false_alarm"] * 3 + ["confirmed_fire", "not_sure", "not_sure"]
    event = with_reports(tmp_path, verdicts, level="High").iloc[0]

    assert event["attention_level"] == "High"  # net false alarms is only 2


def test_level_moves_at_most_one_step_and_stays_in_range(tmp_path):
    raised = with_reports(tmp_path / "a", ["confirmed_fire"] * 6, level="Low").iloc[0]
    capped = with_reports(tmp_path / "b", ["confirmed_fire"] * 2, level="High").iloc[0]

    assert raised["attention_level"] == "Medium"
    assert capped["attention_level"] == "High"
    assert capped["level_change"] == ""


def test_events_are_reordered_by_adjusted_level():
    events = pd.concat([scored_events("High", 75), scored_events("Medium", 60)],
                       ignore_index=True)
    events["latitude"] = [2.8, 5.0]
    events["confirmed_reports"] = [0, 2]
    events["false_alarm_reports"] = [3, 0]

    adjusted = apply_ground_reports(events)

    assert adjusted["attention_level"].tolist() == ["High", "Medium"]
    assert adjusted["satellite_level"].tolist() == ["Medium", "High"]


def test_false_alarm_site_needs_net_reports_when_threshold_is_set(tmp_path):
    store = FeedbackStore(tmp_path / "reports.csv")
    for _ in range(3):
        store.add(3.0, 113.0, "2026-09-03", "false_alarm", "Factory")
    store.add(3.0, 113.0, "2026-09-03", "confirmed_fire")
    reports = store.load()

    assert len(false_alarm_sites(reports, 3)) == 0  # 3 false alarms - 1 confirmation
    assert len(false_alarm_sites(reports, 2)) == 3
    assert len(false_alarm_sites(reports)) == 3  # uploads keep the old rule
