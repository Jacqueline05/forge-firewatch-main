"""Local ground reports: people mark fire events as confirmed or false alarms."""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .places import DISPLAY_UTC_OFFSET, haversine_km


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

# Ground reports can move a fire area's attention level by one step.
# "Net" means confirmed-fire reports minus false-alarm reports; "Not sure"
# counts as neither. Lowering needs more agreement than raising, because
# wrongly downgrading a real fire costs more than checking one extra time.
CONFIRMS_TO_RAISE = 2
FALSE_ALARMS_TO_LOWER = 3
LEVELS = ["Low", "Medium", "High"]


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
    events["confirmed_reports"] = 0
    events["false_alarm_reports"] = 0
    if events.empty or reports.empty:
        return events

    reports = reports.sort_values("reported_at")
    report_dates = pd.to_datetime(reports["event_date"]).dt.date
    window = timedelta(days=MATCH_DAYS)
    for position, event in events.iterrows():
        first = (event["first_seen"] + DISPLAY_UTC_OFFSET).date() - window
        last = (event["last_seen"] + DISPLAY_UTC_OFFSET).date() + window
        near = haversine_km(
            event["latitude"], event["longitude"],
            reports["latitude"].to_numpy(dtype=float),
            reports["longitude"].to_numpy(dtype=float),
        ) <= MATCH_RADIUS_KM
        in_window = report_dates.between(first, last).to_numpy()
        matching = reports[near & in_window]
        if len(matching):
            verdicts = matching["verdict"]
            events.at[position, "confirmed_reports"] = int((verdicts == "confirmed_fire").sum())
            events.at[position, "false_alarm_reports"] = int((verdicts == "false_alarm").sum())
            latest = matching.iloc[-1]
            events.at[position, "ground_report"] = VERDICTS.get(latest["verdict"], "")
            events.at[position, "ground_note"] = latest["note"]
    return events


def apply_ground_reports(events: pd.DataFrame) -> pd.DataFrame:
    """Raise or lower ``attention_level`` one step from net ground reports.

    Expects the columns from :func:`score_events` and :func:`attach_feedback`.
    The satellite-based score is kept; ``satellite_level`` records the level
    before reports and ``level_change`` is "raised", "lowered" or "".
    """
    events = events.copy()
    events["satellite_level"] = events["attention_level"]
    events["level_change"] = ""
    if events.empty:
        return events

    net = events["confirmed_reports"] - events["false_alarm_reports"]
    step = np.select([net >= CONFIRMS_TO_RAISE, net <= -FALSE_ALARMS_TO_LOWER], [1, -1], 0)
    rank = events["attention_level"].map(LEVELS.index).to_numpy()
    new_rank = np.clip(rank + step, 0, len(LEVELS) - 1)
    events["attention_level"] = [LEVELS[i] for i in new_rank]
    events.loc[new_rank > rank, "level_change"] = "raised"
    events.loc[new_rank < rank, "level_change"] = "lowered"

    raised = events["level_change"] == "raised"
    lowered = events["level_change"] == "lowered"
    confirms = events["confirmed_reports"].astype(str)
    alarms = events["false_alarm_reports"].astype(str)
    events.loc[raised, "reasons"] += " · raised by " + confirms[raised] + " confirmed-fire reports"
    events.loc[lowered, "reasons"] += " · lowered by " + alarms[lowered] + " false-alarm reports"
    if "reasons_ms" in events:
        events.loc[raised, "reasons_ms"] += (
            " · dinaikkan oleh " + confirms[raised] + " laporan kebakaran disahkan"
        )
        events.loc[lowered, "reasons_ms"] += (
            " · diturunkan oleh " + alarms[lowered] + " laporan penggera palsu"
        )

    order = events["attention_level"].map(LEVELS.index)
    return (
        events.assign(_order=order)
        .sort_values(["_order", "attention_score", "last_seen"], ascending=False)
        .drop(columns="_order")
        .reset_index(drop=True)
    )


def false_alarm_sites(reports: pd.DataFrame, min_net_reports: int = 1) -> pd.DataFrame:
    """Turn "false alarm" reports into known heat sources for future data.

    A false-alarm report only counts once false-alarm reports within
    ``MATCH_RADIUS_KM`` outnumber confirmed-fire reports there by at least
    ``min_net_reports``.
    """
    false_alarms = reports[reports["verdict"] == "false_alarm"]
    if min_net_reports > 1 and len(false_alarms):
        latitudes = reports["latitude"].to_numpy(dtype=float)
        longitudes = reports["longitude"].to_numpy(dtype=float)
        sign = reports["verdict"].map({"false_alarm": 1, "confirmed_fire": -1}).fillna(0)
        keep = [
            sign[haversine_km(row.latitude, row.longitude, latitudes, longitudes)
                 <= MATCH_RADIUS_KM].sum() >= min_net_reports
            for row in false_alarms.itertuples()
        ]
        false_alarms = false_alarms[keep]
    return pd.DataFrame(
        {
            "name": false_alarms["note"].where(false_alarms["note"] != "", "Reported location"),
            "latitude": false_alarms["latitude"].astype(float),
            "longitude": false_alarms["longitude"].astype(float),
            "radius_km": 1.0,
            "kind": "Reported false alarm",
        }
    )
