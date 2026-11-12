"""A simple, explainable attention score for fire events."""
from __future__ import annotations

import numpy as np
import pandas as pd


# How much each factor contributes to the 0-100 score.
WEIGHTS = {
    "agreement": 35,    # seen by both MODIS and VIIRS
    "persistence": 25,  # still burning after several days
    "peat": 25,         # on peatland (smoulders, produces heavy haze)
    "confidence": 15,   # satellite confidence
}
HIGH_THRESHOLD = 70
MEDIUM_THRESHOLD = 40
FULL_PERSISTENCE_DAYS = 3

LEVEL_MS = {"High": "Tinggi", "Medium": "Sederhana", "Low": "Rendah"}


def _reasons(event: pd.Series, peat_available: bool, language: str) -> str:
    ms = language == "ms"
    reasons = []
    if event["both_satellites"]:
        reasons.append("dikesan kedua-dua satelit" if ms else "seen by both satellites")
    else:
        reasons.append("dikesan satu satelit sahaja" if ms else "seen by one satellite only")
    days = int(event["days_active"])
    if days > 1:
        reasons.append(f"aktif {days} hari" if ms else f"active {days} days")
    else:
        reasons.append("hari pertama" if ms else "first day")
    if peat_available and event["on_peat"]:
        reasons.append("atas tanah gambut" if ms else "on peatland")
    reasons.append(
        f"keyakinan {event['mean_confidence']:.0f}"
        if ms
        else f"confidence {event['mean_confidence']:.0f}"
    )
    return " · ".join(reasons)


def score_events(events: pd.DataFrame, peat_available: bool) -> pd.DataFrame:
    """Add ``attention_score`` (0-100), ``attention_level`` and reasons.

    When no peat layer is loaded the peat factor is left out and the other
    weights are scaled up, so scores are still out of 100.
    """
    events = events.copy()
    if events.empty:
        for column in ("attention_score", "attention_level", "reasons", "reasons_ms"):
            events[column] = pd.Series(dtype=object)
        return events

    factors = {
        "agreement": events["both_satellites"].astype(float),
        "persistence": np.clip(
            (events["days_active"] - 1) / (FULL_PERSISTENCE_DAYS - 1), 0, 1
        ),
        "peat": events["on_peat"].astype(float),
        "confidence": np.clip(events["mean_confidence"] / 100, 0, 1),
    }
    weights = dict(WEIGHTS)
    if not peat_available:
        weights.pop("peat")
    total_weight = sum(weights.values())
    score = sum(factors[name] * weight for name, weight in weights.items())
    events["attention_score"] = (score / total_weight * 100).round().astype(int)
    events["attention_level"] = np.select(
        [
            events["attention_score"] >= HIGH_THRESHOLD,
            events["attention_score"] >= MEDIUM_THRESHOLD,
        ],
        ["High", "Medium"],
        default="Low",
    )
    events["reasons"] = events.apply(_reasons, axis=1, args=(peat_available, "en"))
    events["reasons_ms"] = events.apply(_reasons, axis=1, args=(peat_available, "ms"))
    return events.sort_values(
        ["attention_score", "last_seen"], ascending=[False, False]
    ).reset_index(drop=True)
