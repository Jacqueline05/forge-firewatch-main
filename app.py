import html
import io
from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, str(Path(__file__).parent / "src"))
from firewatch.harmonize import MatchConfig, harmonize  # noqa: E402
from firewatch.filters import filter_observations  # noqa: E402
from firewatch.map_features import (  # noqa: E402
    build_map_features,
    coverage_circle,
)
from firewatch.auth import authenticate  # noqa: E402
from firewatch.loaders import load_observations, quality_score  # noqa: E402
from firewatch.events import EventConfig, build_events  # noqa: E402
from firewatch.false_alarms import (  # noqa: E402
    flag_false_alarms,
    load_known_sources,
)
from firewatch.feedback import (  # noqa: E402
    VERDICTS,
    FeedbackStore,
    attach_feedback,
    false_alarm_sites,
)
from firewatch.firms import (  # noqa: E402
    AREAS,
    MAX_DAY_RANGE,
    FirmsError,
    fetch_live_observations,
)
from firewatch.haze import Wind, WeatherError, fetch_winds, haze_outlook  # noqa: E402
from firewatch.peat import load_peat_layer, points_on_peat  # noqa: E402
from firewatch.places import LOCAL_UTC_OFFSET, compass  # noqa: E402
from firewatch.scoring import LEVEL_MS, score_events  # noqa: E402
from firewatch.summary import format_date, summary_facts  # noqa: E402
from firewatch.game import haze_patrol_html  # noqa: E402


DATA_DIR = Path(__file__).parent / "data"
DATA_PATH = DATA_DIR / "sample_hotspots.csv"
DEMO_PEAT_PATH = DATA_DIR / "demo_peat_illustrative.geojson"
# Put a real peatland GeoJSON here to enable the peat layer for live data.
PEAT_PATH = DATA_DIR / "peatland.geojson"
KNOWN_SOURCES_PATH = DATA_DIR / "known_heat_sources.csv"
DEFAULT_FEEDBACK_PATH = DATA_DIR / "feedback.csv"
# Demo mode: typical south-west monsoon wind (from SW, ~12 km/h).
DEMO_WIND = Wind(speed_kmh=12.0, toward_deg=45.0)
HAZE_EVENT_LIMIT = 15
ATTENTION_COLORS = {"High": "#d62828", "Medium": "#f4a261", "Low": "#8d99ae"}
DATA_SOURCES = ["Demo data", "Live NASA FIRMS", "Upload CSV"]
ARROWS = ["↑", "↗", "→", "↘", "↓", "↙", "←", "↖"]
SUMMARY_TEXT = {
    "en": {
        "title": "Situation summary",
        "active": "Active today",
        "new": "New today",
        "both": "Both satellites",
        "top": "Top fire areas",
        "near": "near",
        "levels": {"High": "HIGH", "Medium": "MEDIUM", "Low": "LOW"},
        "both_tag": "Seen by both satellites",
        "one_tag": "Seen by 1 satellite only",
        "days": "Detected on {n} days",
        "day": "Detected on 1 day",
        "peat": "On peatland",
        "spread": "Spreading {d}",
        "towns": "Smoke may reach (next 24 h)",
        "town": "Town",
        "eta": "Arrival",
        "hours": "~{n} h",
        "none": "No active fire areas on the latest day.",
        "note": "Hotspots are satellite heat signals, not confirmed fires. "
                "Smoke direction is a rough wind-based estimate.",
        "tips": {
            "both": "NASA's MODIS and VIIRS satellites both detected heat here at "
                    "about the same time. Two independent sensors agreeing makes "
                    "a real fire more likely.",
            "one": "Only one of the two satellites (MODIS or VIIRS) detected heat "
                   "here. It may be small, short-lived, hidden by cloud, or a "
                   "false alarm, so it is less certain.",
            "days": "The number of different days (Malaysia Time) on which heat "
                    "was detected here. More days means the fire keeps burning.",
            "peat": "This area is on peat soil. Peat fires smoulder underground "
                    "for weeks and cause most of Borneo's haze.",
            "spread": "The direction the fire has moved between the first and the "
                      "latest day it was detected.",
        },
        "legend": "What do these labels mean?",
        "legend_rows": [
            ("97", "Attention score from 0 to 100. Higher means it needs "
                   "attention sooner (High is 70 or more, Medium 40 to 69)."),
            ("🛰️ Seen by both satellites", "MODIS and VIIRS both saw it: more "
                                           "likely a real fire."),
            ("🛰️ Seen by 1 satellite only", "Only one satellite saw it: less "
                                            "certain, could be a false alarm."),
            ("📅 Detected on 2 days", "Heat was detected on 2 different days: the "
                                     "fire is still burning."),
            ("🟤 On peatland", "Burning on peat soil, which produces heavy haze."),
            ("↗ Spreading north-east", "The direction the fire is moving."),
            ("💨 ~8 h", "Rough time for smoke to reach the town with today's wind."),
        ],
    },
    "ms": {
        "title": "Ringkasan situasi",
        "active": "Aktif hari ini",
        "new": "Baharu hari ini",
        "both": "Kedua-dua satelit",
        "top": "Kawasan kebakaran utama",
        "near": "berhampiran",
        "levels": {"High": "TINGGI", "Medium": "SEDERHANA", "Low": "RENDAH"},
        "both_tag": "Dikesan kedua-dua satelit",
        "one_tag": "Dikesan 1 satelit sahaja",
        "days": "Dikesan selama {n} hari",
        "day": "Dikesan 1 hari",
        "peat": "Atas tanah gambut",
        "spread": "Merebak ke {d}",
        "towns": "Asap mungkin sampai (24 jam)",
        "town": "Bandar",
        "eta": "Tiba",
        "hours": "~{n} jam",
        "none": "Tiada kawasan kebakaran aktif pada hari terkini.",
        "note": "Titik panas ialah isyarat haba satelit, bukan pengesahan "
                "kebakaran. Arah asap ialah anggaran kasar berdasarkan angin.",
        "tips": {
            "both": "Satelit MODIS dan VIIRS NASA kedua-duanya mengesan haba di "
                    "sini pada masa yang hampir sama. Dua pengesan bebas yang "
                    "sepakat menjadikan kebakaran sebenar lebih berkemungkinan.",
            "one": "Hanya satu daripada dua satelit (MODIS atau VIIRS) mengesan "
                   "haba di sini. Mungkin kecil, singkat, dilindungi awan atau "
                   "amaran palsu, jadi kurang pasti.",
            "days": "Bilangan hari berbeza (Waktu Malaysia) haba dikesan di sini. "
                    "Lebih banyak hari bermakna kebakaran masih berterusan.",
            "peat": "Kawasan ini di atas tanah gambut. Kebakaran gambut membara "
                    "di bawah tanah berminggu-minggu dan punca utama jerebu di Borneo.",
            "spread": "Arah kebakaran bergerak antara hari pertama dan hari "
                      "terkini ia dikesan.",
        },
        "legend": "Apakah maksud label ini?",
        "legend_rows": [
            ("97", "Skor perhatian 0 hingga 100. Lebih tinggi bermakna perlu "
                   "diberi perhatian segera (Tinggi 70 ke atas, Sederhana 40 hingga 69)."),
            ("🛰️ Dikesan kedua-dua satelit", "MODIS dan VIIRS kedua-duanya "
                                             "mengesan: lebih berkemungkinan kebakaran sebenar."),
            ("🛰️ Dikesan 1 satelit sahaja", "Hanya satu satelit mengesan: kurang "
                                            "pasti, mungkin amaran palsu."),
            ("📅 Dikesan selama 2 hari", "Haba dikesan pada 2 hari berbeza: "
                                        "kebakaran masih berterusan."),
            ("🟤 Atas tanah gambut", "Terbakar di tanah gambut yang menghasilkan "
                                    "jerebu tebal."),
            ("↗ Merebak ke timur laut", "Arah kebakaran sedang bergerak."),
            ("💨 ~8 jam", "Anggaran masa asap sampai ke bandar dengan angin hari ini."),
        ],
    },
}
MAP_SOURCE_COLORS = {
    "MODIS": "#e76f51",
    "VIIRS": "#2a9d8f",
    "MODIS + VIIRS": "#7651a8",
}
MAP_CIRCLE_COLORS = {
    "MODIS": "rgba(231, 111, 81, 0.14)",
    "VIIRS": "rgba(42, 157, 143, 0.14)",
    "MODIS + VIIRS": "rgba(118, 81, 168, 0.18)",
}


def _map_frame_data(
    map_data: pd.DataFrame, date: str, radius_km: float
) -> list[go.Scattermapbox]:
    frame_data = map_data[map_data["observation_date"] == date]
    traces = []

    for source, color in MAP_SOURCE_COLORS.items():
        group = frame_data[frame_data["source"] == source]
        customdata = pd.DataFrame(
            {
                "id": group["id"].astype(str),
                "source": group["source"].astype(str),
                "region": group["region"].astype(str),
                "observed_at": group["observed_at"].astype(str),
                "match_status": group["match_status"].astype(str),
                "matched_id": group["matched_id"].fillna("None").astype(str),
                "match_distance_km": group["match_distance_km"].map(
                    lambda distance: (
                        f"{distance:.2f} km"
                        if pd.notna(distance)
                        else "Not paired"
                    )
                ),
                "confidence": group["confidence"],
            }
        ).to_numpy()
        traces.append(
            go.Scattermapbox(
                lat=group["latitude"],
                lon=group["longitude"],
                mode="markers",
                name=source,
                marker={
                    "size": 11,
                    "color": color,
                    "opacity": 0.9,
                },
                customdata=customdata,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Satellite: %{customdata[1]}<br>"
                    "Region: %{customdata[2]}<br>"
                    "Observed: %{customdata[3]}<br>"
                    "Status: %{customdata[4]}<br>"
                    "Matched IDs: %{customdata[5]}<br>"
                    "Pair separation: %{customdata[6]}<br>"
                    "Confidence: %{customdata[7]}<br>"
                    f"Coverage radius: {radius_km:.1f} km"
                    "<extra></extra>"
                ),
            )
        )

    for source in MAP_SOURCE_COLORS:
        group = frame_data[frame_data["source"] == source]
        latitudes = []
        longitudes = []
        for row in group.itertuples():
            circle_latitudes, circle_longitudes = coverage_circle(
                row.latitude, row.longitude, radius_km
            )
            latitudes.extend(circle_latitudes + [None])
            longitudes.extend(circle_longitudes + [None])
        traces.append(
            go.Scattermapbox(
                lat=latitudes,
                lon=longitudes,
                mode="lines",
                line={"color": MAP_SOURCE_COLORS[source], "width": 1},
                fill="toself",
                fillcolor=MAP_CIRCLE_COLORS[source],
                hoverinfo="skip",
                showlegend=False,
            )
        )

    return traces


@st.cache_data(show_spinner="Loading observations...")
def load_data(file_bytes: bytes | None) -> pd.DataFrame:
    """Load the uploaded CSV, or the demo data when nothing is uploaded."""
    return load_observations(
        io.BytesIO(file_bytes) if file_bytes is not None else DATA_PATH
    )


@st.cache_data(show_spinner="Downloading the latest NASA FIRMS data...", ttl=1800)
def load_live(map_key: str, area: str, day_range: int) -> pd.DataFrame:
    return fetch_live_observations(map_key, area, day_range)


@st.cache_data(show_spinner="Fetching wind forecast...", ttl=3600)
def load_winds(points: tuple) -> list:
    return fetch_winds(list(points))


@st.cache_resource
def load_peat(path: str, illustrative: bool):
    return load_peat_layer(path, illustrative=illustrative)


@st.cache_data(show_spinner="Matching MODIS and VIIRS signals...")
def run_harmonize(
    observations: pd.DataFrame, max_minutes: int, max_distance_km: float
) -> pd.DataFrame:
    return harmonize(
        observations,
        MatchConfig(max_minutes=max_minutes, max_distance_km=max_distance_km),
    )


st.set_page_config(
    page_title="Borneo FireWatch",
    page_icon="🔥",
    layout="wide",
    # The sidebar works as a hamburger menu: closed until the user opens it.
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 2.5rem; }
    .hero {
        padding: 1.1rem 1.6rem;
        border-radius: .9rem;
        background: linear-gradient(135deg, #073b3a 0%, #0b6e69 55%, #f4a261 140%);
        color: white;
        margin-bottom: 1rem;
    }
    .hero h1 { color: white; margin: 0 0 .15rem 0; padding: 0; font-size: 1.9rem; }
    .hero p { color: #e7f6f2; font-size: .98rem; margin: 0; }
    .eyebrow {
        color: #ffd166; text-transform: uppercase; letter-spacing: .12em;
        font-weight: 700; font-size: .72rem;
    }
    /* Let the sidebar's content fill its height so Sign out can sit at the bottom. */
    [data-testid="stSidebarUserContent"] {
        display: flex;
        flex-direction: column;
        min-height: calc(100vh - 5rem);
    }
    [data-testid="stSidebarUserContent"] > div,
    [data-testid="stSidebarUserContent"] > div > div,
    [data-testid="stSidebarUserContent"] > div > div > div,
    [data-testid="stSidebarUserContent"] > div > div > div > div {
        display: flex;
        flex-direction: column;
        flex: 1 1 auto;
    }
    [data-testid="stVerticalBlockBorderWrapper"]:has(> div > .st-key-signout) {
        margin-top: auto;
        padding-top: .75rem;
    }
    /* Section switcher as frosted-glass pills */
    .st-key-section [role="radiogroup"] {
        gap: .35rem;
        padding: .35rem;
        border-radius: 999px;
        background: rgba(128, 128, 128, .10);
        border: 1px solid rgba(255, 255, 255, .10);
        backdrop-filter: blur(12px) saturate(140%);
        -webkit-backdrop-filter: blur(12px) saturate(140%);
        box-shadow: 0 6px 24px rgba(0, 0, 0, .18), inset 0 1px 0 rgba(255, 255, 255, .08);
        width: fit-content;
        max-width: 100%;
        flex-wrap: nowrap;
        overflow-x: auto;
        margin-bottom: .6rem;
    }
    .st-key-section label[data-baseweb="radio"] {
        margin: 0;
        padding: .5rem 1.05rem;
        border-radius: 999px;
        border: 1px solid transparent;
        cursor: pointer;
        white-space: nowrap;
        transition: background .2s ease, box-shadow .2s ease;
    }
    .st-key-section label[data-baseweb="radio"] > div:first-child { display: none; }
    .st-key-section label[data-baseweb="radio"] p { font-size: .92rem; font-weight: 600; }
    .st-key-section label[data-baseweb="radio"]:hover {
        background: rgba(255, 255, 255, .08);
        border-color: rgba(255, 255, 255, .12);
    }
    .st-key-section label[data-baseweb="radio"]:has(input:checked) {
        background: linear-gradient(135deg, rgba(42, 157, 143, .85), rgba(11, 110, 105, .75) 55%,
                                    rgba(244, 162, 97, .65));
        border-color: rgba(255, 255, 255, .22);
        box-shadow: 0 4px 16px rgba(42, 157, 143, .35), inset 0 1px 0 rgba(255, 255, 255, .25);
    }
    .st-key-section label[data-baseweb="radio"]:has(input:checked) p { color: #fff; }
    @media (max-width: 640px) {
        .st-key-section label[data-baseweb="radio"] { padding: .4rem .7rem; }
        .st-key-section label[data-baseweb="radio"] p { font-size: .82rem; }
    }

    /* Today headline numbers: 4 across on desktop, 2 x 2 on phones */
    .fw-kpis {
        display: grid; grid-template-columns: repeat(4, 1fr); gap: .7rem;
        margin: .2rem 0 1rem;
    }
    .fw-kpi {
        display: flex; align-items: center; gap: .7rem; cursor: help;
        padding: .75rem .9rem; border-radius: .8rem;
        border: 1px solid rgba(128, 128, 128, .22);
        background: rgba(128, 128, 128, .07);
    }
    .fw-kpi-icon { font-size: 1.5rem; }
    .fw-kpi-num { font-size: 1.6rem; font-weight: 700; line-height: 1.1; }
    .fw-kpi-lbl { font-size: .78rem; opacity: .75; }
    @media (max-width: 640px) {
        .fw-kpis { grid-template-columns: repeat(2, 1fr); gap: .5rem; }
        .fw-kpi { padding: .6rem .7rem; }
        .fw-kpi-num { font-size: 1.3rem; }
    }

    .hero-login { margin-top: 2rem; }

    /* Daily summary card */
    .fw-summary {
        border: 1px solid rgba(128, 128, 128, .28);
        border-radius: .9rem;
        padding: 1rem 1.1rem .9rem;
    }
    .fw-head {
        display: flex; justify-content: space-between; align-items: baseline;
        flex-wrap: wrap; gap: .3rem; margin-bottom: .8rem;
    }
    .fw-title { font-weight: 700; font-size: 1.05rem; }
    .fw-date { font-size: .8rem; opacity: .7; font-variant-numeric: tabular-nums; }
    .fw-tiles { display: grid; grid-template-columns: repeat(3, 1fr); gap: .5rem; }
    .fw-tile {
        background: rgba(42, 157, 143, .12);
        border-radius: .6rem; padding: .55rem .4rem; text-align: center;
    }
    .fw-num { font-size: 1.5rem; font-weight: 700; line-height: 1.1; }
    .fw-lbl { font-size: .72rem; opacity: .75; }
    .fw-section {
        margin: 1rem 0 .45rem; font-size: .72rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: .08em; opacity: .7;
    }
    .fw-card {
        border: 1px solid rgba(128, 128, 128, .22); border-left: 4px solid;
        border-radius: .6rem; padding: .55rem .7rem; margin-bottom: .5rem;
    }
    .fw-card-top { display: flex; align-items: center; gap: .5rem; }
    .fw-badge {
        color: #fff; font-size: .65rem; font-weight: 700; letter-spacing: .05em;
        padding: .12rem .45rem; border-radius: 999px;
    }
    .fw-town { font-weight: 700; }
    .fw-dist { font-size: .75rem; opacity: .65; }
    .fw-score { margin-left: auto; font-weight: 700; font-variant-numeric: tabular-nums; }
    .fw-bar {
        height: 5px; border-radius: 999px; background: rgba(128, 128, 128, .2);
        margin: .4rem 0 .45rem; overflow: hidden;
    }
    .fw-bar > div { height: 100%; border-radius: 999px; }
    .fw-tags { display: flex; flex-wrap: wrap; gap: .3rem; }
    .fw-tags span {
        font-size: .72rem; padding: .1rem .5rem; border-radius: 999px;
        background: rgba(128, 128, 128, .14);
    }
    .fw-towns { width: 100%; border-collapse: collapse; font-size: .85rem; }
    .fw-towns th {
        text-align: left; font-size: .7rem; opacity: .65; font-weight: 600;
        padding: 0 .2rem .25rem; border: none;
    }
    .fw-towns td {
        padding: .3rem .2rem; border: none;
        border-top: 1px solid rgba(128, 128, 128, .18);
    }
    .fw-towns .fw-eta { text-align: right; font-variant-numeric: tabular-nums; }
    .fw-note { margin-top: .8rem; font-size: .72rem; opacity: .6; font-style: italic; }
    .fw-tags span[title], .fw-score[title] { cursor: help; }
    .fw-legend {
        margin-top: .9rem; border-radius: .6rem;
        background: rgba(42, 157, 143, .08); padding: .45rem .7rem;
    }
    .fw-legend summary { cursor: pointer; font-size: .8rem; font-weight: 600; }
    .fw-legend table { width: 100%; border-collapse: collapse; margin-top: .4rem; }
    .fw-legend td {
        border: none; padding: .3rem .2rem; font-size: .76rem; vertical-align: top;
        border-top: 1px solid rgba(128, 128, 128, .15);
    }
    .fw-legend .fw-key { white-space: nowrap; font-weight: 600; padding-right: .6rem; }

    /* Hamburger-style menu button (opens the sidebar). */
    [data-testid="stSidebarCollapsedControl"] button svg { display: none; }
    [data-testid="stSidebarCollapsedControl"] button::after {
        content: "☰  Menu";
        font-size: 1rem;
        font-weight: 600;
        white-space: pre;
    }
    [data-testid="stSidebarCollapsedControl"] button {
        width: auto;
        padding: .35rem .8rem;
        border: 1px solid rgba(128, 128, 128, .35);
        border-radius: .5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_secret(name: str) -> str:
    try:
        return str(st.secrets.get(name, ""))
    except FileNotFoundError:
        return ""


def login_screen() -> bool:
    if st.session_state.get("authenticated"):
        return True

    # Banner and form share one centred column so they line up exactly.
    _, form_col, _ = st.columns((1, 1.6, 1))
    form_col.markdown(
        """
        <div class="hero hero-login">
            <div class="eyebrow">FORGEX6 • NASA Space Apps Challenge 2026</div>
            <h1>🔥 Borneo FireWatch</h1>
            <p>A clearer view of MODIS and VIIRS thermal-anomaly observations.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with form_col, st.form("login"):
        st.markdown("#### Sign in")
        username = st.text_input("Username", placeholder="Your team username")
        password = st.text_input(
            "Password", type="password", placeholder="Your team password"
        )
        submitted = st.form_submit_button(
            "Sign in", type="primary", use_container_width=True
        )
        if submitted:
            expected_user = get_secret("FIREWATCH_USERNAME")
            expected_password = get_secret("FIREWATCH_PASSWORD")
            if not expected_user or not expected_password:
                st.error(
                    "Sign-in is not set up yet. Add FIREWATCH_USERNAME and "
                    "FIREWATCH_PASSWORD to the app's secrets."
                )
            elif authenticate(username, password, expected_user, expected_password):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.rerun()
            else:
                st.error("Incorrect username or password. Please try again.")
    return False


if not login_screen():
    st.stop()

st.markdown(
    """
    <div class="hero">
        <div class="eyebrow">FORGEX6 • SARAWAK AND BORNEO</div>
        <h1>🔥 Borneo FireWatch</h1>
        <p>Making satellite heat signals easier for everyone to explore,
        compare and understand.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.expander("Start here: what am I looking at?", expanded=False):
    st.markdown(
        """
        Borneo FireWatch compares heat signals seen by two NASA satellites.
        A dot on the map is a **possible hotspot**, not proof of a fire.

        - **📍 Today** gives a short summary, the fire areas that need
          attention and the towns smoke may drift towards.
        - **🔥 Fire areas** lists each fire area and lets you report what is
          happening on the ground.
        - **🛰️ Satellite signals** shows every heat signal and where MODIS
          and VIIRS agree.
        - Open **☰ Menu** (top left) to choose the data, dates, areas,
          language and filters.
        - Hover over a dot, tag or number to see what it means.
        """
    )

SECTIONS = {
    "today": "📍 Today",
    "fire_areas": "🔥 Fire areas",
    "signals": "🛰️ Satellite signals",
    "game": "🎮 Haze Patrol",
    "guide": "📘 Guide",
}
# Menu data settings only affect these sections; elsewhere they are locked.
DATA_SECTIONS = {"today", "fire_areas", "signals"}
section = st.session_state.get("section", "today")
if section not in SECTIONS:
    section = "today"
locked = section not in DATA_SECTIONS
# The dashboard is English only. (Bahasa Malaysia text for the summary and
# the game is kept in the modules in case a full translation is added later.)
language_code = "en"

st.radio(
    "Section",
    list(SECTIONS),
    format_func=SECTIONS.get,
    horizontal=True,
    key="section",
    label_visibility="collapsed",
)

with st.sidebar:
    if locked:
        st.caption(
            "🔒 Data settings apply to Today, Fire areas and Satellite "
            "signals. Open one of those sections to change them."
        )
    data_source = st.radio(
        "Data source",
        DATA_SOURCES,
        disabled=locked,
        key="data_source",
        help=(
            "Demo data is fictional. Live data downloads the latest MODIS and "
            "VIIRS detections from NASA FIRMS."
        ),
    )
    live_area, live_days, uploaded_file = "Sarawak", 3, None
    if data_source == "Live NASA FIRMS":
        live_area = st.selectbox(
            "Area", list(AREAS), disabled=locked, key="live_area"
        )
        live_days = st.slider(
            "Days of data", 1, MAX_DAY_RANGE, 3, disabled=locked, key="live_days"
        )
    elif data_source == "Upload CSV":
        uploaded_file = st.file_uploader(
            "Upload NASA FIRMS-compatible CSV",
            type=["csv"],
            help="Accepts the project schema or common FIRMS fields such as acq_date.",
            disabled=locked,
            key="upload",
        )
    # Date and area pickers depend on the data, so they are filled in later
    # but keep this position in the sidebar.
    date_area_box = st.container()

    with st.expander("Filters"):
        sources = st.multiselect(
            "Satellites",
            options=["MODIS", "VIIRS"],
            default=["MODIS", "VIIRS"],
            disabled=locked,
            key="sources",
        )
        confidence = st.slider(
            "Minimum confidence",
            0,
            100,
            0,
            help="Higher values show only stronger satellite signals.",
            disabled=locked,
            key="min_confidence",
        )
        hide_false_alarms = st.checkbox(
            "Hide likely false alarms",
            value=False,
            help=(
                "Filters detections FIRMS marks as volcanoes, static industrial "
                "sources or offshore, plus known heat sources and places "
                "reported as false alarms. Detections and reports are retained."
            ),
            disabled=locked,
            key="hide_false_alarms",
        )

    with st.expander("Advanced settings"):
        max_minutes = st.slider(
            "Match time window (minutes)",
            5,
            120,
            30,
            help="MODIS and VIIRS signals this close in time can be paired.",
            disabled=locked,
            key="max_minutes",
        )
        max_distance_km = st.slider(
            "Match distance (km)",
            1.0,
            25.0,
            5.0,
            step=0.5,
            help=(
                "Signals from different satellites within this distance may be "
                "paired. Coverage circles on the signals map use this radius."
            ),
            disabled=locked,
            key="max_distance_km",
        )
        event_link_km = st.slider(
            "Group fire detections within (km)",
            0.5,
            5.0,
            2.0,
            step=0.5,
            help="Nearby detections on consecutive days are treated as one fire.",
            disabled=locked,
            key="event_link_km",
        )
        show_haze = st.checkbox(
            "Show smoke direction",
            value=True,
            help="Uses the Open-Meteo wind forecast (demo mode uses an example wind).",
            disabled=locked,
            key="show_haze",
        )


def sign_out_button() -> None:
    """Draw Sign out as the last item in the sidebar."""
    with st.sidebar:
        with st.container(key="signout"):
            if st.button("Sign out", use_container_width=True):
                st.session_state["authenticated"] = False
                st.session_state.pop("username", None)
                st.rerun()


def stop_page() -> None:
    """Stop the page early, but keep the Sign out button available."""
    sign_out_button()
    st.stop()


def firms_key_help() -> None:
    """Setup steps for the person who runs the app (folded away)."""
    with st.expander("For the project owner: how to switch on live data"):
        st.markdown(
            """
            1. Request a free key at
               <https://firms.modaps.eosdis.nasa.gov/api/map_key/>.
            2. Add it to `.streamlit/secrets.toml` (or the app's **Secrets**
               on Streamlit Cloud): `FIRMS_MAP_KEY = "your-key"`.
            3. Restart the app.
            """
        )


map_key = get_secret("FIRMS_MAP_KEY")
try:
    if locked:
        # The game and guide don't use the filtered data.
        data = load_data(None).iloc[0:0].copy()
    elif data_source == "Live NASA FIRMS":
        if not map_key:
            st.info(
                "**Live data isn't switched on yet.** Choose **Demo data** in "
                "☰ Menu to explore the dashboard in the meantime."
            )
            firms_key_help()
            stop_page()
        data = load_live(map_key, live_area, live_days)
    elif data_source == "Upload CSV":
        if uploaded_file is None:
            st.info(
                "**Upload a CSV file** using **☰ Menu → Upload NASA "
                "FIRMS-compatible CSV**. Files downloaded from NASA FIRMS work "
                "as they are, or use the example below as a template."
            )
            st.download_button(
                "Download example CSV",
                data=DATA_PATH.read_bytes(),
                file_name="firewatch-example.csv",
                mime="text/csv",
            )
            stop_page()
        data = load_data(uploaded_file.getvalue())
    else:
        data = load_data(None)
except (ValueError, FirmsError) as error:
    st.error(f"Data could not be loaded: {error}")
    stop_page()

feedback_store = FeedbackStore(
    get_secret("FIREWATCH_FEEDBACK_PATH") or DEFAULT_FEEDBACK_PATH
)
reports = feedback_store.load()
try:
    known_sources = pd.concat(
        [
            frame
            for frame in (load_known_sources(KNOWN_SOURCES_PATH), false_alarm_sites(reports))
            if not frame.empty
        ]
        or [load_known_sources(KNOWN_SOURCES_PATH)],
        ignore_index=True,
    )
except ValueError as error:
    st.warning(f"Known heat sources could not be loaded: {error}")
    known_sources = false_alarm_sites(reports)
data = flag_false_alarms(data, known_sources)
flagged = data[data["false_alarm_reason"] != ""]
if hide_false_alarms:
    data = data[data["false_alarm_reason"] == ""].copy()

selected_date_range = None
selected_regions = []
if locked:
    with date_area_box:
        st.date_input("Dates", value=None, disabled=True)
        st.multiselect("Areas", ["All areas"], placeholder="All areas", disabled=True)
if not data.empty:
    observation_dates = data["observed_at"].dt.date
    min_date = observation_dates.min()
    max_date = observation_dates.max()
    region_options = sorted(data["region"].dropna().astype(str).unique())
    with date_area_box:
        selected_date_range = st.date_input(
            "Dates",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
        selected_regions = st.multiselect(
            "Areas",
            options=region_options,
            placeholder="All areas",
            help="Leave empty to show every area.",
        ) or region_options

# Last sidebar element on a normal run.
sign_out_button()

if data.empty:
    filtered = data.copy()
elif isinstance(selected_date_range, (tuple, list)):
    if len(selected_date_range) == 1:
        range_start = range_end = selected_date_range[0]
    elif len(selected_date_range) == 2:
        range_start, range_end = selected_date_range
    else:
        range_start = range_end = None

    if range_start is None or range_end is None:
        st.warning("Select both a start and end date.")
        filtered = data.iloc[0:0].copy()
    elif range_start > range_end:
        st.warning("The start date must be on or before the end date.")
        filtered = data.iloc[0:0].copy()
    else:
        filtered = filter_observations(
            data,
            range_start,
            range_end,
            selected_regions,
            sources,
            confidence,
        )
else:
    st.warning("Select a date range.")
    filtered = data.iloc[0:0].copy()

try:
    result = run_harmonize(filtered, max_minutes, max_distance_km)
except ValueError as error:
    st.error(f"Signals could not be matched: {error}")
    st.stop()

is_demo = data_source == "Demo data"
peat_layer = (
    load_peat(str(DEMO_PEAT_PATH), True) if is_demo else load_peat(str(PEAT_PATH), False)
)
result["on_peat"] = (
    points_on_peat(result["latitude"], result["longitude"], peat_layer)
    if peat_layer.available and not result.empty
    else False
)
events, result = build_events(result, EventConfig(link_distance_km=event_link_km))
events = attach_feedback(score_events(events, peat_layer.available), reports)

towns_at_risk = pd.DataFrame(columns=["event_id", "town", "distance_km", "hours_away"])
plumes = pd.DataFrame()
haze_note = ""
if show_haze and not events.empty:
    # Only the fires that matter most, so the map stays readable.
    watched = events[events["attention_level"] == "High"].head(HAZE_EVENT_LIMIT)
    if watched.empty:
        watched = events[events["attention_level"] == "Medium"].head(3)
    if is_demo:
        winds = [DEMO_WIND] * len(watched)
        haze_note = "Demo mode uses an example south-west monsoon wind (12 km/h)."
    else:
        try:
            winds = load_winds(
                tuple(zip(watched["latitude"].round(3), watched["longitude"].round(3)))
            )
            haze_note = "Average wind over the next 24 hours from the Open-Meteo forecast."
        except (WeatherError, ValueError, KeyError) as error:
            winds = []
            haze_note = f"Smoke outlook unavailable: {error}"
    towns_at_risk, plumes = haze_outlook(watched, winds)

matched = int((result["match_status"] == "matched").sum())
matched_pairs = matched // 2
match_rate = (matched / len(result) * 100) if len(result) else 0


def summary_card_html(facts: dict, language: str, peat_available: bool) -> str:
    """Daily summary as a visual card (stat tiles, fire-area cards, towns)."""
    text = SUMMARY_TEXT[language]
    date_text = html.escape(format_date(facts["day"], language))
    tiles = "".join(
        f'<div class="fw-tile"><div class="fw-num">{value}</div>'
        f'<div class="fw-lbl">{label}</div></div>'
        for value, label in (
            (len(facts["active"]), text["active"]),
            (facts["new"], text["new"]),
            (facts["both"], text["both"]),
        )
    )

    cards = []
    for event in facts["top"].itertuples():
        color = ATTENTION_COLORS.get(event.attention_level, "#8d99ae")
        tips = text["tips"]
        # Each tag is (label, explanation shown on hover).
        tags = [
            ("🛰️ " + text["both_tag"], tips["both"])
            if event.both_satellites
            else ("🛰️ " + text["one_tag"], tips["one"]),
            (
                "📅 " + (
                    text["day"] if event.days_active == 1
                    else text["days"].format(n=int(event.days_active))
                ),
                tips["days"],
            ),
        ]
        if peat_available and event.on_peat:
            tags.append(("🟤 " + text["peat"], tips["peat"]))
        if event.spread_direction:
            arrow = ARROWS[int(((event.spread_bearing % 360) + 22.5) // 45) % 8]
            direction = compass(event.spread_bearing, language)
            tags.append(
                (f"{arrow} " + text["spread"].format(d=direction), tips["spread"])
            )
        cards.append(
            f'<div class="fw-card" style="border-left-color:{color}">'
            f'<div class="fw-card-top">'
            f'<span class="fw-badge" style="background:{color}">'
            f'{text["levels"].get(event.attention_level, "")}</span>'
            f'<span class="fw-town">{html.escape(event.nearest_town)}</span>'
            f'<span class="fw-dist">{text["near"]} · {event.town_distance_km:.0f} km</span>'
            f'<span class="fw-score" title="{html.escape(text["legend_rows"][0][1])}">'
            f'{event.attention_score}</span></div>'
            f'<div class="fw-bar"><div style="width:{event.attention_score}%;'
            f'background:{color}"></div></div>'
            f'<div class="fw-tags">'
            + "".join(
                f'<span title="{html.escape(tip)}">{html.escape(label)}</span>'
                for label, tip in tags
            )
            + "</div></div>"
        )

    legend_rows = "".join(
        f"<tr><td class=\"fw-key\">{html.escape(key)}</td><td>{html.escape(meaning)}</td></tr>"
        for key, meaning in text["legend_rows"]
    )
    legend = (
        f'<details class="fw-legend"><summary>ⓘ {text["legend"]}</summary>'
        f"<table>{legend_rows}</table></details>"
    )

    towns = ""
    if len(facts["towns"]):
        rows = "".join(
            f"<tr><td>💨 {html.escape(row.town)}</td>"
            f'<td class="fw-eta">{text["hours"].format(n=f"{row.hours_away:.0f}")}</td></tr>'
            for row in facts["towns"].itertuples()
        )
        towns = (
            f'<div class="fw-section">{text["towns"]}</div>'
            f'<table class="fw-towns"><thead><tr><th>{text["town"]}</th>'
            f'<th class="fw-eta">{text["eta"]}</th></tr></thead><tbody>{rows}</tbody></table>'
        )

    body = "".join(cards) if cards else f'<div class="fw-note">{text["none"]}</div>'
    return (
        '<div class="fw-summary">'
        f'<div class="fw-head"><span class="fw-title">{text["title"]}</span>'
        f'<span class="fw-date">{date_text} · MYT (UTC+08:00)</span></div>'
        f'<div class="fw-tiles">{tiles}</div>'
        f'<div class="fw-section">{text["top"]}</div>{body}{towns}{legend}'
        f'<div class="fw-note">{text["note"]}</div></div>'
    )


def _local_time(series: pd.Series) -> pd.Series:
    return (series + LOCAL_UTC_OFFSET).dt.strftime("%d %b %H:%M")


def events_map(
    events: pd.DataFrame, plumes: pd.DataFrame, peat_layer, height: int = 520
) -> go.Figure:
    figure = go.Figure()
    for rings in peat_layer.polygons:
        outer = rings[0]
        figure.add_trace(
            go.Scattermapbox(
                lon=list(outer[:, 0]),
                lat=list(outer[:, 1]),
                mode="lines",
                fill="toself",
                fillcolor="rgba(121, 85, 61, 0.18)",
                line={"color": "rgba(121, 85, 61, 0.6)", "width": 1},
                hoverinfo="skip",
                name="Peatland" + (" (illustrative)" if peat_layer.illustrative else ""),
                legendgroup="peat",
                showlegend=rings is peat_layer.polygons[0],
            )
        )
    for plume in plumes.itertuples():
        figure.add_trace(
            go.Scattermapbox(
                lon=[plume.longitude, plume.end_longitude],
                lat=[plume.latitude, plume.end_latitude],
                mode="lines+markers",
                line={"color": "rgba(90, 90, 90, 0.7)", "width": 2},
                marker={"size": [0, 9], "color": "rgba(90, 90, 90, 0.9)"},
                hoverinfo="text",
                text=f"{plume.event_id}: smoke drift in 24 h at {plume.wind_kmh:.0f} km/h",
                name="Smoke drift (24 h)",
                legendgroup="plume",
                showlegend=plume.Index == 0,
            )
        )
    for level, color in ATTENTION_COLORS.items():
        group = events[events["attention_level"] == level]
        if group.empty:
            continue
        figure.add_trace(
            go.Scattermapbox(
                lat=group["latitude"],
                lon=group["longitude"],
                mode="markers",
                marker={
                    "size": (10 + group["detections"].clip(upper=20) * 1.5).tolist(),
                    "color": color,
                    "opacity": 0.9,
                },
                name=f"{level} attention",
                customdata=group[
                    ["event_id", "nearest_town", "attention_score", "reasons",
                     "days_active", "detections"]
                ].to_numpy(),
                hovertemplate=(
                    "<b>%{customdata[0]}</b> near %{customdata[1]}<br>"
                    "Attention score: %{customdata[2]}<br>"
                    "%{customdata[3]}<br>"
                    "%{customdata[5]} detections over %{customdata[4]} day(s)"
                    "<extra></extra>"
                ),
            )
        )
    figure.update_layout(
        mapbox={
            "style": "open-street-map",
            "center": {
                "lat": float(events["latitude"].mean()),
                "lon": float(events["longitude"].mean()),
            },
            "zoom": 5.2,
        },
        height=height,
        margin=dict(t=0, b=0, l=0, r=0),
        legend={"orientation": "h", "y": -0.02},
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return figure


if section == "today":
    notes = []
    if is_demo:
        notes.append("Demo mode: fictional fires, illustrative peat areas and an example wind.")
    if len(flagged):
        notes.append(
            f"{len(flagged)} likely false alarm(s) "
            + ("hidden." if hide_false_alarms else "shown.")
        )
    if notes:
        st.caption(" ".join(notes))

    has_events = not events.empty
    kpis = [
        ("🔥", len(events), "Fire areas",
         "Nearby detections over several days grouped into one fire area."),
        ("🚨", int((events["attention_level"] == "High").sum()) if has_events else 0,
         "High attention", "Fire areas with an attention score of 70 or more."),
        ("🟤", int(events["on_peat"].sum()) if peat_layer.available and has_events else "n/a",
         "On peatland",
         "Demo uses illustrative peat areas, not real boundaries."
         if is_demo else "Needs a peat map (data/peatland.geojson)."),
        ("💨", towns_at_risk["town"].nunique() if len(towns_at_risk) else 0,
         "Towns in smoke path", "Towns downwind of high-attention fires in the next 24 hours."),
    ]
    st.markdown(
        '<div class="fw-kpis">'
        + "".join(
            f'<div class="fw-kpi" title="{html.escape(tip)}">'
            f'<div class="fw-kpi-icon">{icon}</div>'
            f'<div><div class="fw-kpi-num">{value}</div>'
            f'<div class="fw-kpi-lbl">{label}</div></div></div>'
            for icon, value, label, tip in kpis
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    if not has_events:
        st.info("No fire areas match the current filters.")
    else:
        summary_col, map_col = st.columns((2, 3), gap="large")
        with summary_col:
            st.markdown(
                summary_card_html(
                    summary_facts(events, towns_at_risk, peat_layer.available),
                    language_code,
                    peat_layer.available,
                ),
                unsafe_allow_html=True,
            )
        with map_col:
            st.plotly_chart(
                events_map(events, plumes, peat_layer, height=480),
                use_container_width=True,
            )
            st.caption(
                "Bigger circles mean more detections. Grey lines show where smoke "
                "could drift in 24 hours. " + haze_note
            )

if section == "fire_areas":
    if events.empty:
        st.info(
            "No fire areas match the current filters. Try widening the dates or "
            "areas in ☰ Menu."
        )
    else:
        st.caption(
            "Each row is one fire area: detections close together on nearby "
            "days. Most urgent first. Hover a column name for details."
        )
        level_text = events["attention_level"]
        if language_code == "ms":
            level_text = level_text.map(LEVEL_MS)
        level_dots = events["attention_level"].map(
            {"High": "🔴", "Medium": "🟠", "Low": "⚪"}
        ).fillna("")
        table = pd.DataFrame(
            {
                "ID": events["event_id"],
                "Attention": level_dots + " " + level_text,
                "Score": events["attention_score"],
                "Near": events["nearest_town"],
                "Days": events["days_active"],
                "Both satellites": events["both_satellites"],
                "On peat": events["on_peat"],
                "Last seen": _local_time(events["last_seen"]),
                "Ground report": events["ground_report"].replace("", "–"),
            }
        )
        if not peat_layer.available:
            table = table.drop(columns="On peat")
        st.dataframe(
            table,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Score": st.column_config.ProgressColumn(
                    "Score", min_value=0, max_value=100, format="%d",
                    help="0-100: satellite agreement, days burning, peatland, confidence.",
                ),
                "ID": st.column_config.TextColumn(
                    help="Short name for the fire area, used when sending a report."
                ),
                "Days": st.column_config.NumberColumn(
                    help="Number of different days heat was detected here."
                ),
                "Both satellites": st.column_config.CheckboxColumn(
                    help="Ticked when MODIS and VIIRS both saw it (more likely a real fire)."
                ),
                "On peat": st.column_config.CheckboxColumn(
                    help="Ticked when the fire is on peat soil (heavy haze)."
                ),
                "Ground report": st.column_config.TextColumn(
                    help="Latest report from people on the ground, if any."
                ),
                "Last seen": st.column_config.TextColumn(
                    help="Malaysia Time (MYT, UTC+08:00)."
                ),
            },
        )
        st.download_button(
            "Download full table (CSV)",
            data=events.to_csv(index=False).encode("utf-8"),
            file_name="borneo-firewatch-fire-areas.csv",
            mime="text/csv",
        )

        if st.session_state.pop("report_saved", False):
            st.success("Thank you. The report has been saved.")
        with st.expander("📝 Report what is happening on the ground"):
            st.caption(
                "Confirm a fire or mark a false alarm. False-alarm places are "
                "flagged automatically in future data."
            )
            with st.form("ground_report", clear_on_submit=True):
                labels = {
                    f"{row.event_id} · near {row.nearest_town} · {row.attention_level}": row
                    for row in events.itertuples()
                }
                choice = st.selectbox("Fire area", list(labels))
                verdict = st.radio(
                    "What did you find?",
                    list(VERDICTS),
                    format_func=VERDICTS.get,
                    horizontal=True,
                )
                note = st.text_input(
                    "Note (optional)",
                    placeholder="e.g. smallholder land clearing, gas flare",
                )
                if st.form_submit_button("Submit report", type="primary"):
                    event = labels[choice]
                    feedback_store.add(
                        event.latitude,
                        event.longitude,
                        (event.last_seen + LOCAL_UTC_OFFSET).date().isoformat(),
                        verdict,
                        note,
                        st.session_state.get("username", ""),
                    )
                    st.session_state["report_saved"] = True
                    st.rerun()
        if len(reports):
            with st.expander(f"Previous reports ({len(reports)})"):
                st.dataframe(
                    reports.assign(verdict=reports["verdict"].map(VERDICTS)),
                    hide_index=True,
                    use_container_width=True,
                )

if section == "signals":
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Signals shown", len(result), help="Total heat signals after filters.")
    col2.metric(
        "Pairs seen by both", matched_pairs,
        help="MODIS and VIIRS signals close in time and place.",
    )
    col3.metric(
        "Agreement rate", f"{match_rate:.0f}%",
        help="Share of signals that are part of a MODIS/VIIRS pair.",
    )
    col4.metric(
        "Data quality", f"{quality_score(data)}%",
        help="Share of basic checks passed: valid times, coordinates, satellite "
             "names and unique IDs.",
    )

    map_mode = st.radio(
        "Map style",
        ["Individual signals", "Signal concentration"],
        horizontal=True,
        label_visibility="collapsed",
    )
    if result.empty:
        st.info(
            "No signals match the current filters. Try widening the dates, "
            "areas or filters in ☰ Menu."
        )
    else:
        map_data = build_map_features(result)
        map_data["observation_date"] = map_data["observed_at"].dt.strftime("%Y-%m-%d")
        center = {
            "lat": float(map_data["latitude"].mean()),
            "lon": float(map_data["longitude"].mean()),
        }
        if map_mode == "Signal concentration":
            map_chart = px.density_mapbox(
                map_data,
                lat="latitude",
                lon="longitude",
                z="confidence",
                labels={"confidence": "Confidence"},
                radius=28,
                center=center,
                zoom=5,
                height=520,
                mapbox_style="open-street-map",
                color_continuous_scale=[
                    "#073b3a",
                    "#2a9d8f",
                    "#f4a261",
                    "#e76f51",
                ],
            )
        else:
            dates = sorted(map_data["observation_date"].unique())
            map_chart = go.Figure(data=_map_frame_data(
                map_data, dates[0], max_distance_km
            ))
            map_chart.frames = [
                go.Frame(
                    data=_map_frame_data(map_data, date, max_distance_km),
                    name=date,
                    traces=list(range(6)),
                )
                for date in dates
            ]
            if len(dates) > 1:
                map_chart.update_layout(
                    updatemenus=[
                        {
                            "type": "buttons",
                            "showactive": False,
                            "buttons": [
                                {
                                    "label": "Play",
                                    "method": "animate",
                                    "args": [
                                        None,
                                        {
                                            "frame": {
                                                "duration": 700,
                                                "redraw": True,
                                            },
                                            "transition": {"duration": 250},
                                            "fromcurrent": True,
                                        },
                                    ],
                                },
                                {
                                    "label": "Pause",
                                    "method": "animate",
                                    "args": [
                                        [None],
                                        {
                                            "frame": {
                                                "duration": 0,
                                                "redraw": False,
                                            },
                                            "mode": "immediate",
                                        },
                                    ],
                                },
                            ],
                        }
                    ],
                    sliders=[
                        {
                            "active": 0,
                            "steps": [
                                {
                                    "label": date,
                                    "method": "animate",
                                    "args": [
                                        [date],
                                        {
                                            "mode": "immediate",
                                            "frame": {
                                                "duration": 0,
                                                "redraw": True,
                                            },
                                            "transition": {"duration": 0},
                                        },
                                    ],
                                }
                                for date in dates
                            ],
                        }
                    ],
                )
        map_chart.update_layout(
            margin=dict(t=0, b=0, l=0, r=0),
            legend_title_text="Satellite source",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        if map_mode == "Individual signals":
            map_chart.update_layout(
                mapbox={
                    "style": "open-street-map",
                    "center": center,
                    "zoom": 5,
                },
                height=520,
            )
        st.plotly_chart(map_chart, use_container_width=True)
        if map_mode == "Individual signals":
            st.caption(
                f"The small center dot stays readable; its {max_distance_km:.1f} km "
                "coverage circle scales with map zoom "
                f"({max_distance_km * 2:.1f} km diameter). Close MODIS and "
                "VIIRS detections are shown once at their midpoint; hover to "
                "see their measured separation. Use the timeline to replay "
                "signals by date."
            )
        else:
            st.caption(
                "This view highlights areas where stronger signals cluster. It "
                "does not represent burned area or fire intensity."
            )

if section == "signals":
    with st.expander("Charts and data table"):
        left, right = st.columns((1.25, 1))
        with left:
            st.subheader("Observation trends")
            daily = (
                result.assign(date=result["observed_at"].dt.date)
                .groupby(["date", "source"], as_index=False)
                .size()
                .rename(columns={"size": "observations"})
            )
            chart = px.line(
                daily,
                x="date",
                y="observations",
                color="source",
                markers=True,
                color_discrete_map=MAP_SOURCE_COLORS,
            )
            chart.update_layout(legend_title_text="Satellite")
            st.plotly_chart(chart, use_container_width=True)

        with right:
            st.subheader("Confidence by source")
            confidence_chart = px.box(
                result,
                x="source",
                y="confidence",
                color="source",
                points="all",
                color_discrete_map=MAP_SOURCE_COLORS,
            )
            confidence_chart.update_layout(
                showlegend=False, yaxis_title="Confidence score"
            )
            st.plotly_chart(confidence_chart, use_container_width=True)

        st.subheader("Regional activity comparison")
        regional = (
            result.groupby(["region", "source"], as_index=False)
            .size()
            .rename(columns={"size": "observations"})
        )
        region_chart = px.bar(
            regional,
            x="region",
            y="observations",
            color="source",
            barmode="group",
            text_auto=True,
            color_discrete_map={"MODIS": "#e76f51", "VIIRS": "#2a9d8f"},
        )
        region_chart.update_layout(
            xaxis_title="Study region",
            yaxis_title="Observations",
            legend_title_text="Satellite source",
        )
        st.plotly_chart(region_chart, use_container_width=True)

        st.subheader("Harmonization results")
        status_counts = (
            result["match_status"]
            .value_counts()
            .rename_axis("status")
            .reset_index(name="count")
        )
        status_col, table_col = st.columns((0.8, 1.7))
        with status_col:
            status_chart = px.pie(
                status_counts,
                names="status",
                values="count",
                hole=0.45,
                color_discrete_sequence=["#2a9d8f", "#f4a261", "#e76f51"],
            )
            status_chart.update_layout(
                showlegend=True, margin=dict(t=10, b=10, l=10, r=10)
            )
            st.plotly_chart(status_chart, use_container_width=True)

        with table_col:
            st.dataframe(
                result[
                    [
                        "id",
                        "source",
                        "observed_at",
                        "region",
                        "confidence",
                        "match_status",
                        "matched_id",
                        "match_distance_km",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
            st.download_button(
                "Download filtered results",
                data=result.to_csv(index=False).encode("utf-8"),
                file_name="borneo-firewatch-harmonized-results.csv",
                mime="text/csv",
            )

if section == "game":
    components.html(haze_patrol_html(language_code), height=600)
    st.caption(
        "Haze Patrol is a practice game with made-up fires. Your best score "
        "is saved in this browser only."
    )

if section == "guide":
    st.subheader("How the attention score works")
    st.markdown(
        """
        Each fire area gets a score from 0 to 100:

        | Factor | Points | Why it matters |
        |---|---|---|
        | Seen by both MODIS and VIIRS | 35 | Two sensors agreeing makes a real fire likelier |
        | Burning for several days (full at 3) | 25 | Lasting fires are rarely false alarms |
        | On peatland | 25 | Peat fires smoulder for weeks and cause most of Borneo's haze |
        | Satellite confidence | 15 | The satellites' own confidence in the detection |

        **High** is 70 or more, **Medium** 40 to 69. When no peat layer is
        loaded, the peat points are left out and the other factors are scaled
        up to 100.

        **Smoke direction** is a straight-line estimate using the average
        10 m wind over the next 24 hours (Open-Meteo forecast). It is not an
        air-quality forecast; check official APIMS readings for actual air
        quality.
        """
    )
    st.subheader("Data sources")
    st.markdown(
        """
        - **Hotspots:** NASA FIRMS MODIS and VIIRS (S-NPP, NOAA-20, NOAA-21)
          near-real-time and archive data.
        - **Wind:** Open-Meteo forecast API.
        - **Peatland:** add a peatland GeoJSON as `data/peatland.geojson`
          (for example a Borneo extract of a published peatland map). The
          demo uses illustrative areas only.
        - **Known heat sources:** `data/known_heat_sources.csv`, plus places
          reported as false alarms in the Fire areas tab.
        """
    )
    st.subheader("How should this result be interpreted?")
    st.markdown(
        """
        **Matched** means MODIS and VIIRS signals fall within the selected time
        and distance thresholds. It is a candidate relationship, not
        confirmation that both satellites observed the same fire.

        Use the confidence filter to focus the review, compare source coverage,
        and download evidence for team discussion. A hotspot is a thermal
        anomaly and should be verified with authoritative sources before
        operational decisions.
        """
    )
    st.subheader("About the project")
    st.write(
        "Borneo FireWatch is an exploratory FORGEX6 prototype for Sarawak and "
        "Borneo. It runs on fictional demonstration data by default and can "
        "load live NASA FIRMS data when a FIRMS MAP_KEY is configured."
    )
    st.subheader("Data safety note")
    st.info(
        "A hotspot is not proof of a fire, burned area, or haze concentration. "
        "This dashboard supports exploration and communication, not emergency "
        "response or official fire verification."
    )
