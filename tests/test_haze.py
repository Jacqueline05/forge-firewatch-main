import json

import pandas as pd
import pytest

from src.firewatch.haze import Wind, average_wind, fetch_winds, haze_outlook


def event(event_id, lat, lon, level="High"):
    return {"event_id": event_id, "latitude": lat, "longitude": lon, "attention_level": level}


def test_average_wind_converts_from_direction_to_drift_direction():
    wind = average_wind([10, 10], [225, 225])  # from the south-west

    assert wind.speed_kmh == pytest.approx(10)
    assert wind.toward_deg == pytest.approx(45)


def test_opposite_winds_cancel_out():
    assert average_wind([10, 10], [0, 180]).speed_kmh == pytest.approx(0, abs=1e-9)


def test_town_downwind_is_at_risk_and_upwind_town_is_not():
    events = pd.DataFrame([event("E1", 2.805, 112.205)])  # near Mukah

    towns, plumes = haze_outlook(events, [Wind(12, 45)])

    assert "Bintulu" in towns["town"].tolist()  # north-east, ~100 km
    assert "Sibu" not in towns["town"].tolist()  # south-west, upwind
    bintulu = towns.set_index("town").loc["Bintulu"]
    assert bintulu["hours_away"] == pytest.approx(bintulu["distance_km"] / 12)
    assert len(plumes) == 1


def test_calm_wind_gives_no_outlook():
    events = pd.DataFrame([event("E1", 2.805, 112.205)])

    towns, plumes = haze_outlook(events, [Wind(0.5, 45)])

    assert towns.empty and plumes.empty


def test_fetch_winds_reads_open_meteo_multi_location_response():
    now = pd.Timestamp.now(tz="UTC").floor("h").tz_localize(None)
    times = [
        (now + pd.Timedelta(hours=hour)).strftime("%Y-%m-%dT%H:%M")
        for hour in range(-2, 46)
    ]
    location = {
        "hourly": {
            "time": times,
            "wind_speed_10m": [10.0] * len(times),
            "wind_direction_10m": [270.0] * len(times),  # from the west
        }
    }
    urls = []

    def fetch(url):
        urls.append(url)
        return json.dumps([location, location])

    winds = fetch_winds([(2.8, 112.2), (1.5, 110.3)], fetch=fetch)

    assert len(winds) == 2
    assert winds[0].toward_deg == pytest.approx(90)
    assert "latitude=2.8000%2C1.5000" in urls[0]
