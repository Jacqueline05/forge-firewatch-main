from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from firewatch.harmonize import MatchConfig, harmonize


DATA_PATH = Path(__file__).parent / "data" / "sample_hotspots.csv"

st.set_page_config(page_title="Borneo FireWatch", page_icon="🔥", layout="wide")
st.title("🔥 Borneo FireWatch")
st.caption("FORGEX6 • MODIS and VIIRS hotspot harmonization prototype")

data = pd.read_csv(DATA_PATH)
data["observed_at"] = pd.to_datetime(data["observed_at"], utc=True)

with st.sidebar:
    st.header("Filters")
    sources = st.multiselect(
        "Satellite source",
        options=["MODIS", "VIIRS"],
        default=["MODIS", "VIIRS"],
    )
    confidence = st.slider("Minimum confidence", 0, 100, 0)
    max_minutes = st.slider("Matching time window (minutes)", 5, 120, 30)

filtered = data[
    data["source"].isin(sources) & (data["confidence"] >= confidence)
].copy()
result = harmonize(filtered, MatchConfig(max_minutes=max_minutes))

matched = int((result["match_status"] == "matched").sum())
col1, col2, col3 = st.columns(3)
col1.metric("Observations", len(result))
col2.metric("Potential matches", matched // 2)
col3.metric("Regions represented", result["region"].nunique())

st.subheader("Unified hotspot map")
st.map(result, latitude="latitude", longitude="longitude", color="#ff4b4b")

left, right = st.columns(2)
with left:
    st.subheader("Daily observations")
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
        title="Observations by source",
    )
    st.plotly_chart(chart, use_container_width=True)

with right:
    st.subheader("Harmonization results")
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
