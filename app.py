from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from firewatch.harmonize import MatchConfig, harmonize  # noqa: E402
from firewatch.auth import authenticate  # noqa: E402


DATA_PATH = Path(__file__).parent / "data" / "sample_hotspots.csv"

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
        <p>Harmonizing satellite observations to make potential fire activity
        easier to explore, compare, and explain.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

data = pd.read_csv(DATA_PATH)
data["observed_at"] = pd.to_datetime(data["observed_at"], utc=True)

with st.sidebar:
    st.header("Explore the data")
    st.caption("Adjust the analysis thresholds and compare observation sources.")
    sources = st.multiselect(
        "Satellite source",
        options=["MODIS", "VIIRS"],
        default=["MODIS", "VIIRS"],
    )
    confidence = st.slider("Minimum confidence", 0, 100, 0)
    max_minutes = st.slider("Matching time window (minutes)", 5, 120, 30)
    if st.button("Sign out"):
        st.session_state["authenticated"] = False
        st.rerun()

filtered = data[
    data["source"].isin(sources) & (data["confidence"] >= confidence)
].copy()
result = harmonize(filtered, MatchConfig(max_minutes=max_minutes))

matched = int((result["match_status"] == "matched").sum())
matched_pairs = matched // 2
match_rate = (matched / len(result) * 100) if len(result) else 0
col1, col2, col3, col4 = st.columns(4)
col1.metric("Observations", len(result))
col2.metric("Potential matches", matched_pairs)
col3.metric("Match rate", f"{match_rate:.0f}%")
col4.metric("Regions represented", result["region"].nunique())

st.subheader("Unified hotspot map")
if result.empty:
    st.warning("No observations match the current filters.")
else:
    st.map(result, latitude="latitude", longitude="longitude", color="#ff4b4b")

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

st.info(
    "A hotspot is a detected thermal anomaly, not confirmation of a fire. "
    "This prototype uses demonstration data until official NASA FIRMS data "
    "access and challenge requirements are confirmed."
)
