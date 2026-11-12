from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from firewatch.harmonize import MatchConfig, harmonize  # noqa: E402
from firewatch.filters import filter_observations  # noqa: E402
from firewatch.map_features import (  # noqa: E402
    build_map_features,
    coverage_circle,
)
from firewatch.auth import authenticate  # noqa: E402


DATA_PATH = Path(__file__).parent / "data" / "sample_hotspots.csv"
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
    [data-testid="stSidebarUserContent"] > div[data-testid="stVerticalBlock"] {
        display: flex;
        flex-direction: column;
        min-height: calc(100vh - 2rem);
    }
    .st-key-sidebar-signout {
        position: sticky;
        bottom: 0;
        z-index: 2;
        margin-top: auto;
        padding-top: 0.75rem;
        background: var(--background-color);
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
        - Hover over a dot to see its confidence and match distance.
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
        "What match and coverage radius should we use?",
        1.0,
        25.0,
        5.0,
        step=0.5,
        help=(
            "Signals from different satellites within this distance may be "
            "paired. Each map coverage circle uses this as its radius."
        ),
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

try:
    data = load_observations(uploaded_file)
except ValueError as error:
    st.error(f"Data could not be loaded: {error}")
    st.stop()

selected_date_range = None
selected_regions = []
if not data.empty:
    observation_dates = data["observed_at"].dt.date
    min_date = observation_dates.min()
    max_date = observation_dates.max()
    region_options = sorted(data["region"].dropna().astype(str).unique())
    with st.sidebar:
        st.subheader("Date and region")
        selected_date_range = st.date_input(
            "Observation date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            help="Choose the observation dates to include.",
        )
        selected_regions = st.multiselect(
            "Which regions should we show?",
            options=region_options,
            default=region_options,
            help="Choose one or more regions.",
        )

with st.sidebar:
    with st.container(key="sidebar-signout"):
        if st.button("Sign out", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()

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

result = harmonize(
    filtered,
    MatchConfig(max_minutes=max_minutes, max_distance_km=max_distance_km),
)

matched = int((result["match_status"] == "matched").sum())
matched_pairs = matched // 2
match_rate = (matched / len(result) * 100) if len(result) else 0
overview_tab, analysis_tab, guide_tab = st.tabs(
    ["Overview", "Explore signals", "Guide and methodology"]
)

with overview_tab:
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Signals shown", len(result), help="Total heat signals after filters.")
    col2.metric("Signals seen by both", matched_pairs)
    col3.metric("Agreement rate", f"{match_rate:.0f}%")
    col4.metric("Areas represented", result["region"].nunique())
    col5.metric("Data quality", f"{quality_score(data)}%")

    if result.empty:
        st.warning("No signals match the current filters. Try widening the thresholds.")
    elif match_rate >= 50:
        st.success(
            f"Insight: {match_rate:.0f}% of filtered signals participate in a "
            "potential cross-satellite match."
        )
    else:
        st.info(
            f"Insight: {match_rate:.0f}% of filtered signals participate in a "
            "potential match; source coverage differs in this view."
        )

    st.subheader("Unified hotspot map")
    if result.empty:
        st.warning("No signals are available for the map.")
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
                radius=28,
                center=center,
                zoom=4,
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
                    "zoom": 4,
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

with analysis_tab:
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

with guide_tab:
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
        "Borneo. It uses demonstration data until official NASA FIRMS access "
        "and challenge requirements are confirmed."
    )
    st.subheader("Data safety note")
    st.info(
        "A hotspot is not proof of a fire, burned area, or haze concentration. "
        "This dashboard supports exploration and communication, not emergency "
        "response or official fire verification."
    )
