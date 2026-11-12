from datetime import date

import pytest

from src.firewatch.firms import (
    FirmsError,
    area_url,
    fetch_live_observations,
    history_counts,
)


MODIS_CSV = (
    "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,"
    "instrument,confidence,version,bright_t31,frp,daynight\n"
    "2.8,112.2,330.1,1.0,1.0,2026-09-01,530,Terra,MODIS,78,6.1NRT,300.0,12.5,D\n"
)
VIIRS_CSV = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,"
    "instrument,confidence,version,bright_ti5,frp,daynight\n"
    "2.8008,112.2009,339.6,0.4,0.4,2026-09-01,540,N,VIIRS,h,2.0NRT,290.0,8.1,D\n"
    "4.4,114.0,331.0,0.4,0.4,2026-09-01,545,N,VIIRS,n,2.0NRT,288.0,3.2,D\n"
)
EMPTY_CSV = "latitude,longitude,bright_ti4,acq_date,acq_time,satellite,instrument,confidence\n"


def fake_fetch(responses):
    calls = []

    def fetch(url):
        calls.append(url)
        for product, text in responses.items():
            if f"/{product}/" in url:
                return text
        return EMPTY_CSV

    fetch.calls = calls
    return fetch


def test_area_url_uses_bbox_day_range_and_start_date():
    url = area_url("KEY", "MODIS_SP", (109.5, 0.8, 115.8, 5.1), 10, date(2019, 9, 1))

    assert url.endswith("/KEY/MODIS_SP/109.5,0.8,115.8,5.1/10/2019-09-01")


def test_area_url_rejects_more_than_ten_days():
    with pytest.raises(ValueError):
        area_url("KEY", "MODIS_NRT", (0, 0, 1, 1), 11)


def test_live_observations_combine_products_with_unique_ids():
    fetch = fake_fetch({"MODIS_NRT": MODIS_CSV, "VIIRS_SNPP_NRT": VIIRS_CSV})

    observations = fetch_live_observations("KEY", "Sarawak", 2, fetch=fetch)

    assert len(fetch.calls) == 4
    assert len(observations) == 3
    assert observations["id"].is_unique
    assert sorted(observations["source"]) == ["MODIS", "VIIRS", "VIIRS"]
    assert sorted(observations["confidence"]) == [60, 78, 90]
    assert set(observations["region"]) == {"Mukah", "Miri"}


def test_invalid_key_gives_readable_error():
    with pytest.raises(FirmsError, match="Invalid MAP_KEY"):
        fetch_live_observations("BAD", fetch=lambda url: "Invalid MAP_KEY.")


def test_no_detections_gives_empty_frame():
    observations = fetch_live_observations("KEY", fetch=fake_fetch({}))

    assert observations.empty
    assert "observed_at" in observations


def test_history_compares_same_window_each_year():
    header, row = MODIS_CSV.splitlines()

    def fetch(url):
        year = int(url.rsplit("/", 1)[1][:4])
        rows = 5 if year == 2019 else 1
        return header + "\n" + (row + "\n") * rows

    history = history_counts("KEY", "Sarawak", date(2026, 9, 10), years=8, fetch=fetch)

    assert history["year"].tolist() == list(range(2019, 2027))
    assert history.set_index("year").loc[2019, "detections"] == 5
    assert history["current"].tolist() == [False] * 7 + [True]
    assert history["window"].iloc[-1] == "01 Sep - 10 Sep"
