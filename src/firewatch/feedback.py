"""Local ground reports: people mark fire events as confirmed or false alarms."""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from .places import LOCAL_UTC_OFFSET, haversine_km


FEEDBACK_COLUMNS = [
    "reported_at", "event_date", "latitude", "longitude",
    "verdict", "note", "reported_by",
]
VERDICTS = {
    "confirmed_fire": "Confirmed fire",
    "false_alarm": "False alarm",
    "not_sure": "Not sure",
}
# A report applies to events within this distance...
MATCH_RADIUS_KM = 2.0
# ...that were active within this many days of the reported date.
MATCH_DAYS = 3


class FeedbackStore:
    """Append-only CSV store of ground reports."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> pd.DataFrame:
        if not self.path.exists():
            return pd.DataFrame(columns=FEEDBACK_COLUMNS)
        reports = pd.read_csv(self.path, dtype={"note": str, "reported_by": str})
        reports["note"] = reports["note"].fillna("")
        return reports

    def add(
        self,
        latitude: float,
        longitude: float,
        event_date: str,
        verdict: str,
        note: str = "",
        reported_by: str = "",
    ) -> None:
        if verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {sorted(VERDICTS)}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not self.path.exists()
        with self.path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FEEDBACK_COLUMNS)
            if is_new:
                writer.writeheader()
            writer.writerow(
                {
                    "reported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "event_date": event_date,
                    "latitude": round(float(latitude), 5),
                    "longitude": round(float(longitude), 5),
                    "verdict": verdict,
                    "note": note.strip(),
                    "reported_by": reported_by,
                }
            )


def attach_feedback(events: pd.DataFrame, reports: pd.DataFrame) -> pd.DataFrame:
    """Add ``ground_report`` and ``ground_note`` from the latest nearby report."""
    events = events.copy()
    events["ground_report"] = ""
    events["ground_note"] = ""
    if events.empty or reports.empty:
        return events

    reports = reports.sort_values("reported_at")
    report_dates = pd.to_datetime(reports["event_date"]).dt.date
    window = timedelta(days=MATCH_DAYS)
    for position, event in events.iterrows():
        first = (event["first_seen"] + LOCAL_UTC_OFFSET).date() - window
        last = (event["last_seen"] + LOCAL_UTC_OFFSET).date() + window
        near = haversine_km(
            event["latitude"], event["longitude"],
            reports["latitude"].to_numpy(dtype=float),
            reports["longitude"].to_numpy(dtype=float),
        ) <= MATCH_RADIUS_KM
        in_window = report_dates.between(first, last).to_numpy()
        matching = reports[near & in_window]
        if len(matching):
            latest = matching.iloc[-1]
            events.at[position, "ground_report"] = VERDICTS.get(latest["verdict"], "")
            events.at[position, "ground_note"] = latest["note"]
    return events


def false_alarm_sites(reports: pd.DataFrame) -> pd.DataFrame:
    """Turn "false alarm" reports into known heat sources for future data."""
    false_alarms = reports[reports["verdict"] == "false_alarm"]
    return pd.DataFrame(
        {
            "name": false_alarms["note"].where(false_alarms["note"] != "", "Reported location"),
            "latitude": false_alarms["latitude"].astype(float),
            "longitude": false_alarms["longitude"].astype(float),
            "radius_km": 1.0,
            "kind": "Reported false alarm",
        }
    )
