# FORGEX6 — Borneo FireWatch

> Six Minds. One Mission. A Clearer View of Earth.

Borneo FireWatch is an exploratory data platform for comparing MODIS and VIIRS
thermal-anomaly observations across Sarawak and Borneo. It focuses on
transparent harmonization rather than treating every satellite hotspot as a
confirmed fire.

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

### 4. Configure team login

Copy the example secrets file:

```bash
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

On macOS/Linux, use:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml` and set the username and password shared by
the project owner. Never commit this file to GitHub.

### 5. Start the dashboard

```bash
streamlit run app.py
```

Open the local URL shown in the terminal, usually
`http://localhost:8501`, then sign in with the configured team credentials.

### 6. Run the quality checks

```bash
pytest -q
flake8 app.py src tests
```

## What the MVP demonstrates

- Standardizes compatible MODIS and VIIRS observation fields
- Matches observations using configurable time and geographic thresholds
- Pairs each detection with at most one nearest cross-satellite observation
- Shows the measured MODIS/VIIRS separation and a coverage circle on the map
- Classifies records as matched, MODIS-only, or VIIRS-only
- Filters observations by date, region, satellite source, and confidence
- Displays a map and daily trend chart in Streamlit
- Provides a team login screen and sign-out control
- Shows confidence distributions, match-rate KPIs, and match-status breakdowns
- Validates the harmonization logic with pytest

## Run locally (quick reference)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

### Configure team login

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and set a
team username and password. The real `secrets.toml` file is ignored by Git and
must never be committed.

For Streamlit Cloud, add `FIREWATCH_USERNAME` and `FIREWATCH_PASSWORD` under
the app's **Secrets** settings. This login protects the dashboard interface;
GitHub repository access is managed separately through private-repository
collaborators.

Run the checks:

```bash
pytest -q
flake8 app.py src tests
```

## Repository structure

```text
├── app.py                         # Streamlit dashboard
├── data/sample_hotspots.csv       # Fictional demonstration records
├── src/firewatch/harmonize.py     # Cleaning and matching engine
├── tests/test_harmonize.py        # Unit tests
├── .github/workflows/ci.yml       # Lint and test automation
└── docs/                          # Architecture and data notes
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

## Planned NASA FIRMS integration

1. Confirm the official NASA Space Apps 2026 challenge requirements.
2. Obtain authorized MODIS and VIIRS data through NASA FIRMS.
3. Map source fields into the schema documented in
   [`docs/data-contract.md`](docs/data-contract.md).
4. Run validation checks for coordinates, timestamps, confidence, and
   duplicate records.
5. Re-run the test suite before publishing dashboard results.

## Important limitations

Satellite hotspots indicate detected thermal anomalies. They do not, by
themselves, confirm a fire's cause, establish burned area, or measure haze
concentration. Borneo FireWatch is an exploratory information tool and is not
a replacement for official fire verification, emergency response, or
air-quality monitoring.

## Team

**FORGEX6** — six working adults and university students collaborating on the
NASA Space Apps Challenge 2026 project.

Team representative and member details should be added after the team agrees
on what may be publicly shared.
