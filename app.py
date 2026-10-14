from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from firewatch.harmonize import MatchConfig, harmonize  # noqa: E402
from firewatch.auth import authenticate  # noqa: E402


DATA_PATH = Path(__file__).parent / "data" / "sample_hotspots.csv"


def load_observations(uploaded_file=None) -> pd.DataFrame:
    """Load demo data or normalize common NASA FIRMS CSV fields."""
    observations = pd.read_csv(uploaded_file or DATA_PATH)
    columns = {column.lower(): column for column in observations.columns}

    if "source" not in observations and columns.get("satellite"):
        observations["source"] = observations[columns["satellite"]].map(
            lambda value: "MODIS"
            if str(value).upper() in {"MODIS", "TERRA", "AQUA"}
            else "VIIRS"
        )
    if "observed_at" not in observations and columns.get("acq_date"):
        time_column = columns.get("acq_time")
        times = (
            observations[time_column].fillna(0).astype(str).str.zfill(4)
            if time_column
            else "0000"
        )
        observations["observed_at"] = pd.to_datetime(
            observations[columns["acq_date"]].astype(str)
            + " "
            + times.str[:2]
            + ":"
            + times.str[2:]
            + ":00",
            errors="coerce",
            utc=True,
        )
    if "confidence" not in observations and columns.get("confidence"):
        confidence = observations[columns["confidence"]]
        observations["confidence"] = confidence.astype(str).str.lower().map(
            {"l": 30, "n": 60, "h": 90}
        ).fillna(pd.to_numeric(confidence, errors="coerce"))
    if "region" not in observations:
        observations["region"] = "Borneo"
    if "id" not in observations:
        observations["id"] = [f"OBS-{i:04d}" for i in range(len(observations))]

    required = ["id", "source", "observed_at", "latitude", "longitude", "confidence"]
    missing = [column for column in required if column not in observations]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    observations["observed_at"] = pd.to_datetime(
        observations["observed_at"], errors="coerce", utc=True
    )
    return observations.dropna(subset=required).copy()


def quality_score(observations: pd.DataFrame) -> int:
    checks = [
        observations["observed_at"].notna().all(),
        observations["latitude"].between(-90, 90).all(),
        observations["longitude"].between(-180, 180).all(),
        observations["source"].isin({"MODIS", "VIIRS"}).all(),
        observations["id"].is_unique,
    ]
    return round(sum(checks) / len(checks) * 100)


st.set_page_config(
    page_title="Borneo FireWatch",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .hero {
        padding: 2rem 2.2rem;
        border-radius: 1rem;
        background: linear-gradient(135deg, #073b3a 0%, #0b6e69 55%, #f4a261 140%);
        color: white;
        margin-bottom: 1.5rem;
    }
    .hero h1 { color: white; margin-bottom: .3rem; }
    .hero p { color: #e7f6f2; font-size: 1.05rem; }
    .eyebrow { color: #ffd166; text-transform: uppercase; letter-spacing: .12em; font-weight: 700; }
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

    st.markdown(
        """
        <div class="hero">
            <div class="eyebrow">FORGEX6 • NASA Space Apps Challenge 2026</div>
            <h1>🔥 Borneo FireWatch</h1>
            <p>A clearer view of MODIS and VIIRS thermal-anomaly observations.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("login"):
        st.subheader("Team access")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            valid = authenticate(
                username,
                password,
                get_secret("FIREWATCH_USERNAME"),
                get_secret("FIREWATCH_PASSWORD"),
            )
            if valid:
                st.session_state["authenticated"] = True
                st.rerun()
            st.error("Invalid credentials or login is not configured.")
    st.caption("Team members should use the credentials provided by the project owner.")
    return False


if not login_screen():
    st.stop()

st.markdown(
    """
    <div class="hero">
        <div class="eyebrow">FORGEX6 • SARAWAK AND BORNEO</div>
        <h1>🔥 Borneo FireWatch</h1>
        <p>Making satellite heat signals easier for everyone to explore,
        compare, and understand.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.expander("Start here: what am I looking at?", expanded=True):
    st.markdown(
        """
        Borneo FireWatch compares heat signals seen by two NASA satellites.
        A dot on the map is a **possible hotspot**, not proof of a fire.

        - **Colors** show which satellite detected the signal.
        - **Larger dots** represent higher satellite confidence.
        - **Matched** means both satellites saw signals close together in
          time and location.
        - Use the filters on the left to ask simple questions, such as
          “Where do both satellites agree?”
        """
    )

with st.sidebar:
    st.header("Explore the map")
    st.caption("Use these simple controls to focus the story you want to see.")
    sources = st.multiselect(
        "Which satellite signals should we show?",
        options=["MODIS", "VIIRS"],
        default=["MODIS", "VIIRS"],
        help="Choose one or both satellite sources.",
    )
    confidence = st.slider(
        "How certain should a signal be?",
        0,
        100,
        0,
        help="Higher values show only stronger satellite signals.",
    )
    max_minutes = st.slider(
        "How close in time should signals be?",
        5,
        120,
        30,
        help="This helps compare signals detected near the same time.",
    )
    max_distance_km = st.slider(
        "How close on the map?",
        1.0,
        25.0,
        5.0,
        step=0.5,
        help="This helps compare signals detected near the same place.",
    )
    map_mode = st.radio(
        "How should we show the map?",
        ["Individual signals", "Signal concentration"],
        help="Use individual signals for detail or concentration to see patterns.",
    )
    uploaded_file = st.file_uploader(
        "Upload NASA FIRMS-compatible CSV",
        type=["csv"],
        help="Accepts the project schema or common FIRMS fields such as acq_date.",
    )
    if st.button("Sign out"):
        st.session_state["authenticated"] = False
        st.rerun()

try:
    data = load_observations(uploaded_file)
except ValueError as error:
    st.error(f"Data could not be loaded: {error}")
    st.stop()

filtered = data[
    data["source"].isin(sources) & (data["confidence"] >= confidence)
].copy()
result = harmonize(
    filtered,
    MatchConfig(max_minutes=max_minutes, max_distance_km=max_distance_km),
)

matched = int((result["match_status"] == "matched").sum())
matched_pairs = matched // 2
match_rate = (matched / len(result) * 100) if len(result) else 0
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Signals shown", len(result), help="Total satellite heat signals after filters.")
col2.metric("Signals seen by both", matched_pairs)
col3.metric("Agreement rate", f"{match_rate:.0f}%")
col4.metric("Areas represented", result["region"].nunique())
col5.metric("Data quality", f"{quality_score(data)}%")

if result.empty:
    st.warning("No observations match the current filters. Try widening the thresholds.")
elif match_rate >= 50:
    st.success(
        f"Insight: {match_rate:.0f}% of filtered observations participate in a "
        "potential cross-satellite match."
    )
else:
    st.info(
        f"Insight: {match_rate:.0f}% of filtered observations participate in a "
        "potential match; source coverage differs in this view."
    )

st.subheader("Unified hotspot map")
if result.empty:
    st.warning("No observations match the current filters.")
else:
    map_data = result.copy()
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
            radius=28,
            center=center,
            zoom=4,
            height=520,
            mapbox_style="open-street-map",
            color_continuous_scale=["#073b3a", "#2a9d8f", "#f4a261", "#e76f51"],
        )
    else:
        map_chart = px.scatter_mapbox(
            map_data,
            lat="latitude",
            lon="longitude",
            color="source",
            size="confidence",
            hover_name="id",
            hover_data=["region", "observed_at", "match_status", "confidence"],
            animation_frame="observation_date",
            size_max=28,
            center=center,
            zoom=4,
            height=520,
            mapbox_style="open-street-map",
            color_discrete_map={"MODIS": "#e76f51", "VIIRS": "#2a9d8f"},
        )
    map_chart.update_layout(
        margin=dict(t=0, b=0, l=0, r=0),
        legend_title_text="Satellite source",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    map_chart.update_traces(marker={"opacity": 0.88})
    st.plotly_chart(map_chart, use_container_width=True)
    if map_mode == "Individual signals":
        st.caption(
            "Use the timeline controls to replay signals by date. Marker size "
            "shows confidence; color identifies the satellite source."
        )
    else:
        st.caption(
            "This view highlights areas where stronger signals cluster. It does "
            "not represent burned area or fire intensity."
        )

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
        template="plotly_white",
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
        template="plotly_white",
    )
    confidence_chart.update_layout(showlegend=False, yaxis_title="Confidence score")
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
    template="plotly_white",
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
    result["match_status"].value_counts().rename_axis("status").reset_index(name="count")
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
    status_chart.update_layout(showlegend=True, margin=dict(t=10, b=10, l=10, r=10))
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

with st.expander("Glossary and responsible use"):
    st.markdown(
        """
        **Matched** means MODIS and VIIRS observations fall within the selected
        time and distance thresholds. It is a candidate relationship, not
        confirmation that both satellites observed the same fire.

        Use the confidence filter to focus the review, compare source coverage,
        and download the filtered evidence for team discussion. A hotspot is a
        thermal anomaly and should be verified with authoritative sources before
        operational decisions.
        """
    )

st.info(
    "A hotspot is a detected thermal anomaly, not confirmation of a fire. "
    "This prototype uses demonstration data until official NASA FIRMS data "
    "access and challenge requirements are confirmed."
)
