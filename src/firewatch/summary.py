"""Plain-language daily summary in English or Bahasa Malaysia."""
from __future__ import annotations

import pandas as pd

from .places import LOCAL_UTC_OFFSET, compass
from .scoring import LEVEL_MS


MONTHS_MS = [
    "Januari", "Februari", "Mac", "April", "Mei", "Jun", "Julai",
    "Ogos", "September", "Oktober", "November", "Disember",
]


def _format_date(day, language: str) -> str:
    if language == "ms":
        return f"{day.day} {MONTHS_MS[day.month - 1]} {day.year}"
    return f"{day.day} {day:%B %Y}"


def _event_line(event: pd.Series, language: str, peat_available: bool) -> str:
    ms = language == "ms"
    near = (
        f"Berhampiran **{event['nearest_town']}** ({event['town_distance_km']:.0f} km)"
        if ms
        else f"Near **{event['nearest_town']}** ({event['town_distance_km']:.0f} km)"
    )
    level = event["attention_level"]
    parts = [
        f"perhatian {LEVEL_MS.get(level, level).lower()} ({event['attention_score']})"
        if ms
        else f"{level.lower()} attention ({event['attention_score']})",
        event["reasons_ms"] if ms else event["reasons"],
    ]
    if event.get("spread_direction"):
        direction = compass(event["spread_bearing"], language)
        parts.append(
            f"merebak ke arah {direction} ({event['spread_km']:.1f} km)"
            if ms
            else f"spreading {direction} ({event['spread_km']:.1f} km)"
        )
    if event.get("ground_report"):
        parts.append(
            f"laporan lapangan: {event['ground_report'].lower()}"
            if ms
            else f"ground report: {event['ground_report'].lower()}"
        )
    return f"- {near}: " + "; ".join(parts)


def summary_facts(
    events: pd.DataFrame,
    towns_at_risk: pd.DataFrame,
    peat_available: bool = False,
    top: int = 3,
) -> dict:
    """Numbers behind the daily summary, for text or graphic display.

    Covers the latest day in the data (Malaysia Time). ``peat`` is None when
    no peat layer is loaded.
    """
    latest_day = (events["last_seen"].max() + LOCAL_UTC_OFFSET).date()
    first_days = (events["first_seen"] + LOCAL_UTC_OFFSET).dt.date
    last_days = (events["last_seen"] + LOCAL_UTC_OFFSET).dt.date
    active = events[last_days == latest_day]
    risky = (
        towns_at_risk[towns_at_risk["event_id"].isin(active["event_id"])]
        if len(towns_at_risk)
        else towns_at_risk
    )
    return {
        "day": latest_day,
        "active": active,
        "new": int((first_days[last_days == latest_day] == latest_day).sum()),
        "high": int((active["attention_level"] == "High").sum()),
        "both": int(active["both_satellites"].sum()),
        "peat": int(active["on_peat"].sum()) if peat_available else None,
        "top": active.sort_values("attention_score", ascending=False).head(top),
        "towns": (
            risky.sort_values("hours_away").drop_duplicates("town").head(5)
            if len(risky)
            else risky
        ),
    }


def format_date(day, language: str = "en") -> str:
    return _format_date(day, language)


def daily_summary(
    events: pd.DataFrame,
    towns_at_risk: pd.DataFrame,
    language: str = "en",
    peat_available: bool = False,
    top: int = 3,
) -> str:
    """Return a short Markdown summary of the latest day in the data."""
    ms = language == "ms"
    if events.empty:
        return (
            "Tiada titik panas aktif dalam pilihan semasa."
            if ms
            else "No active hotspots in the current selection."
        )

    facts = summary_facts(events, towns_at_risk, peat_available, top)
    active, new, high, both, peat = (
        facts["active"], facts["new"], facts["high"], facts["both"], facts["peat"]
    )
    date_text = _format_date(facts["day"], language)

    if ms:
        lines = [
            f"**Ringkasan {date_text}** (MYT, UTC+08:00)",
            "",
            f"**{len(active)}** kawasan kebakaran aktif, **{new}** baharu hari ini. "
            f"**{high}** memerlukan perhatian tinggi, **{both}** dikesan oleh "
            "kedua-dua satelit"
            + (f", **{peat}** atas tanah gambut." if peat is not None else "."),
        ]
    else:
        lines = [
            f"**Summary for {date_text}** (MYT, UTC+08:00)",
            "",
            f"**{len(active)}** active fire areas, **{new}** new today. "
            f"**{high}** need high attention, **{both}** seen by both satellites"
            + (f", **{peat}** on peatland." if peat is not None else "."),
        ]

    if len(facts["top"]):
        lines += ["", "**Kawasan utama:**" if ms else "**Top areas:**"]
        lines += [
            _event_line(event, language, peat_available)
            for _, event in facts["top"].iterrows()
        ]

    if len(facts["towns"]):
        towns = ", ".join(
            f"{row.town} (~{row.hours_away:.0f} " + ("jam)" if ms else "h)")
            for row in facts["towns"].itertuples()
        )
        lines += [
            "",
            (f"**Asap mungkin bergerak ke arah:** {towns}"
             if ms else f"**Smoke may drift towards:** {towns}"),
        ]

    lines += [
        "",
        (
            "_Titik panas ialah anomali haba yang dikesan satelit, bukan "
            "pengesahan kebakaran. Arah asap ialah anggaran kasar berdasarkan angin._"
            if ms
            else "_Hotspots are satellite heat signals, not confirmed fires. "
            "Smoke direction is a rough wind-based estimate._"
        ),
    ]
    return "\n".join(lines)
