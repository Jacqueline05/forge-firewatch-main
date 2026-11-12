import pandas as pd

from src.firewatch.events import build_events
from src.firewatch.harmonize import harmonize
from src.firewatch.haze import Wind, haze_outlook
from src.firewatch.loaders import load_observations
from src.firewatch.peat import load_peat_layer, points_on_peat
from src.firewatch.scoring import score_events
from src.firewatch.summary import daily_summary


def demo_pipeline(peat_available=True):
    result = harmonize(load_observations("data/sample_hotspots.csv"))
    layer = load_peat_layer("data/demo_peat_illustrative.geojson", illustrative=True)
    result["on_peat"] = points_on_peat(result["latitude"], result["longitude"], layer)
    events, _ = build_events(result)
    events = score_events(events, peat_available=peat_available)
    events["ground_report"] = ""
    towns, _ = haze_outlook(events, [Wind(12, 45)] * len(events))
    return events, towns


def test_english_summary_describes_latest_day():
    events, towns = demo_pipeline()

    text = daily_summary(events, towns, "en", peat_available=True)

    assert "Summary for 4 September 2026" in text
    assert "Near **Mukah**" in text
    assert "on peatland" in text
    assert "Bintulu" in text
    assert "not confirmed fires" in text


def test_malay_summary_uses_malay_wording():
    events, towns = demo_pipeline()

    text = daily_summary(events, towns, "ms", peat_available=True)

    assert "Ringkasan 4 September 2026" in text
    assert "Berhampiran **Mukah**" in text
    assert "tanah gambut" in text
    assert "merebak ke arah timur laut" in text
    assert "bukan pengesahan kebakaran" in text


def test_summary_without_peat_layer_does_not_mention_peat():
    events, towns = demo_pipeline(peat_available=False)

    assert "peat" not in daily_summary(events, towns, "en", peat_available=False)


def test_empty_summary():
    assert "No active hotspots" in daily_summary(pd.DataFrame(), pd.DataFrame(), "en")
