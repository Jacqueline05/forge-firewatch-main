# FORGEX6 — Forge Firewatch

> Six Minds. One Mission. A Clearer View of Earth.

Forge Firewatch is an exploratory data platform for comparing MODIS and VIIRS
thermal-anomaly observations around the world. Live NASA FIRMS queries support
worldwide coverage and custom geographic bounding boxes. Fictional
demonstration hotspots and illustrative peat shapes cover Borneo and several
other regions. The system focuses on transparent harmonization rather than
treating every satellite hotspot as a confirmed fire.

## Project status

**MVP prototype.** The current version uses clearly labelled demonstration
data so the team can validate the workflow before connecting an official NASA
FIRMS data source and API credentials.

## Start from GitHub

### 1. Clone the repository

Make sure you have Git and Python 3.11 or newer installed.

```bash
git clone https://github.com/Jacqueline05/Borneo-FireWatch.git
cd Borneo-FireWatch
```

Because the repository is private, each team member must first accept the
GitHub collaboration invitation.

### 2. Create and activate a virtual environment

**Windows PowerShell**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS/Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure secrets (optional)

Copy the example secrets file:

```bash
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

On macOS/Linux, use:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml` to add an optional NASA FIRMS key. Never commit
this file to GitHub.

### 5. Start the dashboard

```bash
streamlit run app.py
```

Open the local URL shown in the terminal, usually
`http://localhost:8501`, then click **Enter**.

### 6. Run the quality checks

```bash
pytest -q
flake8 app.py src tests
```

## What the MVP demonstrates

**Fire intelligence for selected locations**

- **Fire areas:** groups detections close in place and time into one fire,
  with how many days it has burned and which direction it is spreading
- **Peatland flag:** marks fires on peat (needs a peat layer for your study
  area, see below)
- **Attention score (0-100):** combines satellite agreement, persistence,
  peatland and confidence, with a plain explanation for each fire
- **Smoke direction outlook:** lists towns downwind of active fires in the
  next 24 hours using the Open-Meteo wind forecast
- **Daily situation summary** card for the latest day
- **🎮 Haze Patrol:** a 60-second arcade game about fires, peat, wind and haze (with pause and stop)
- **Ground reports:** users can confirm a fire or mark a false alarm; false
  alarm locations are flagged automatically in future data
- **False-alarm filter:** hides FIRMS volcano/industrial/offshore detections,
  known heat sources, and reported false alarms

**Data area:** Demo data defaults to **World** and includes fictional fires
from several regions; **Borneo** is available as a focused demo area. Live
NASA FIRMS defaults to worldwide coverage, with Sarawak, Borneo, and custom
bounding boxes also available. Global queries default to one day to keep
downloads manageable.

**Satellite comparison (Signals map and Explore signals tabs)**

- Matches MODIS and VIIRS observations using configurable time and distance
- Pairs each detection with at most one nearest cross-satellite observation
- Classifies records as matched, MODIS-only, or VIIRS-only
- Filters by date, region, satellite source, and confidence
- Map with timeline, trend, confidence and regional charts, CSV download

## Optional data and keys

| What | How to enable |
|---|---|
| Live NASA FIRMS data | Request a free key at <https://firms.modaps.eosdis.nasa.gov/api/map_key/> and set `FIRMS_MAP_KEY` in `.streamlit/secrets.toml` |
| Peatland layer for live data | Save a peatland map for your study area as `data/peatland.geojson` (WGS84 polygons). The demo uses illustrative areas in several regions in `data/demo_peat_illustrative.geojson`, which are **not** real peat boundaries |
| Known heat sources | Add verified gas flares, factories, etc. to `data/known_heat_sources.csv` |
| Where ground reports are saved | Defaults to `data/feedback.csv` (not committed). On Streamlit Cloud the file resets when the app restarts; set `FIREWATCH_FEEDBACK_PATH` to persistent storage to keep reports |

The wind forecast (Open-Meteo) needs no key.

## Run locally (quick reference)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

### Opening the dashboard

The dashboard opens on a welcome banner with a single **Enter** button; no
username or password is needed.

Run the checks:

```bash
pytest -q
flake8 app.py src tests
```

## Repository structure

```text
├── app.py                              # Streamlit dashboard
├── data/
│   ├── sample_hotspots.csv             # Fictional demonstration records
│   ├── demo_peat_illustrative.geojson  # Illustrative peat areas (demo only)
│   └── known_heat_sources.csv          # Verified non-fire heat sources
├── src/firewatch/
│   ├── loaders.py                      # CSV / FIRMS field normalization
│   ├── harmonize.py                    # MODIS/VIIRS matching engine
│   ├── filters.py                      # Date, region, source filters
│   ├── events.py                       # Group detections into fire areas
│   ├── peat.py                         # Peatland point-in-polygon check
│   ├── scoring.py                      # Attention score
│   ├── haze.py                         # Wind forecast and smoke outlook
│   ├── summary.py                      # Daily situation summary
│   ├── game.py, haze_patrol.html       # Haze Patrol game
│   ├── feedback.py                     # Ground reports
│   ├── false_alarms.py                 # Known heat sources, FIRMS type
│   ├── firms.py                        # NASA FIRMS live data API
│   ├── places.py                       # Settlement labels and geography helpers
│   └── map_features.py                 # Map pairs and coverage circles
├── tests/                              # Unit tests (pytest)
├── .github/workflows/ci.yml            # Lint and test automation
└── docs/                               # Architecture and data notes
```

## Harmonization approach

Records are considered potential matches when they are within the configured
time window and geographic radius. Each detection is paired with at most one
nearest cross-satellite observation, and the measured separation is included
in the harmonized results. On the map, a matched pair appears once at its
midpoint. Coverage circles use the selected geographic threshold as the
radius, so their diameter is twice that distance. Matching is an analytical
convenience, not proof that two records represent the same physical fire or
that a circle represents burned area.

The dashboard explicitly distinguishes:

- **Matched:** observations that satisfy the matching thresholds
- **MODIS only:** a record with no compatible VIIRS observation
- **VIIRS only:** a record with no compatible MODIS observation

## Next steps

1. Load a real peatland map for the study area as `data/peatland.geojson`.
2. Fill `data/known_heat_sources.csv` with verified industrial heat sources.
3. Choose persistent storage for ground reports before wider use.
4. Confirm the official NASA Space Apps 2026 challenge requirements.

## Important limitations

Satellite hotspots indicate detected thermal anomalies. They do not, by
themselves, confirm a fire's cause, establish burned area, or measure haze
concentration. Forge Firewatch is an exploratory information tool and is not
a replacement for official fire verification, emergency response, or
air-quality monitoring. Times are displayed in UTC. The smoke outlook uses a
representative set of cities worldwide; each fire is labeled with the
nearest listed city and its distance, even when that city is far away. The smoke direction outlook is a
rough straight-line estimate from the average wind, not an air-quality
forecast.

## Team

**FORGEX6** — six working adults and university students collaborating on the
NASA Space Apps Challenge 2026 project.

Team representative and member details should be added after the team agrees
on what may be publicly shared.
