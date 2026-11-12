# Borneo FireWatch features

This document describes every feature in the current MVP. The dashboard runs
on fictional demonstration data by default and can load live NASA FIRMS data
when a `FIRMS_MAP_KEY` is configured. All times are Malaysia Time (MYT,
UTC+08:00).

## Dashboard layout

- **Sign in** with the team username and password (Streamlit secrets).
- **Compact banner** with the project name and tagline.
- **"Start here: what am I looking at?"** — a short guide, collapsed by
  default.
- **☰ Menu** (top left) holds all settings. It starts closed so the page
  opens on the content.
- **Six sections** in a frosted-glass switcher; the selected one glows in
  the banner's teal-to-orange gradient:
  📍 Today · 🔥 Fire areas · 🛰️ Satellite signals · 📈 Past years ·
  🎮 Haze Patrol · 📘 Guide. Only the open section is drawn, so pages load
  quickly, and the switcher stays available even when a data source still
  needs setting up.
- The sign-in banner and form share one centred column.
- The dashboard is in English.

## ☰ Menu (settings)

Always visible:

- **Data source:** Demo data, Live NASA FIRMS (choose Sarawak or Borneo and
  1-10 days), or Upload CSV.
- **Dates:** observation date range.
- **Areas:** pick towns/regions; leave empty for all areas.

Folded away:

- **Filters:** satellites (MODIS, VIIRS), minimum confidence, and "Hide
  likely false alarms" (on by default).
- **Advanced settings:** match time window (5-120 min), match distance
  (1-25 km), fire grouping distance (0.5-5 km), and smoke direction on/off.

The data settings (data source, dates, areas, filters and advanced
settings) only affect 📍 Today, 🔥 Fire areas and 🛰️ Satellite signals. In
📈 Past years, 🎮 Haze Patrol and 📘 Guide they are greyed out with a 🔒 note,
and the choices are kept for when you return.

**Sign out** is always the last item at the bottom of the menu and works in
every section and data mode.

## 📍 Today

- **Headline numbers:** fire areas, high-attention areas, areas on peatland,
  and towns in the smoke path.
- **Situation summary card** for the latest day:
  - Date with MYT (UTC+08:00).
  - Tiles: active today, new today, seen by both satellites.
  - **Top fire area cards** with a coloured attention badge (HIGH / MEDIUM /
    LOW), nearest town and distance, score with a score bar, and tags:
    🛰️ Seen by both satellites / Seen by 1 satellite only, 📅 Detected on
    N days, 🟤 On peatland, ↗ Spreading (direction).
  - **Smoke may reach (next 24 h):** towns with approximate arrival time.
  - Hovering a tag or score explains it, and **"ⓘ What do these labels
    mean?"** opens a key that also works on phones.
- **Fire areas map:** circles coloured by attention level and sized by the
  number of detections, peatland areas shaded, and grey lines showing where
  smoke could drift in 24 hours. Smoke lines are drawn only for high-attention
  fires (or the top medium ones when there is no high) to keep the map clear.
- A short note in demo mode and a count of hidden likely false alarms.

## 🔥 Fire areas

- Table of all fire areas: area ID, attention level, score bar, nearest town,
  days detected, seen by both satellites, on peat, last seen (MYT) and ground
  report. Column headers have explanations on hover.
- **Download full table (CSV)** with every field, including spread direction
  and distance, detections per satellite and the reasons behind each score.
- **Report what is happening on the ground** (folded form): choose a fire
  area, mark it Confirmed fire / False alarm / Not sure, and add a note. The
  signed-in username is recorded. Previous reports are listed below.

## 🛰️ Satellite signals

- Numbers: signals shown, MODIS/VIIRS pairs, agreement rate, data quality.
- **Map** in two styles:
  - *Individual signals:* MODIS, VIIRS and matched pairs (shown once at their
    midpoint) with a coverage circle of the match distance, plus a date
    timeline with Play/Pause.
  - *Signal concentration:* heat map of where stronger signals cluster.
- **Charts and data table** (folded): daily trend, confidence by satellite,
  activity by region, match-status breakdown, the full matched-results table,
  and a CSV download. MODIS is always orange and VIIRS teal.

## 📈 Past years

- Compares MODIS detections in the same 10-day window for each of the last
  11 years (MODIS has a consistent record since 2000; 2015 and 2019 were major
  haze years).
- Shows this year's count, the past-year average and the difference, with a
  bar chart and average line.
- Needs a `FIRMS_MAP_KEY`; uses archive data (`MODIS_SP`) for past years and
  near-real-time data (`MODIS_NRT`) for this year.

## 🎮 Haze Patrol

A 60-second arcade game on a stylised map of Sarawak, built on the same ideas
as the dashboard. Works with mouse or touch, on desktop and phones.

- **Tap fires** to drop water; small fires give bonus points and quick
  saves build a combo (up to x3).
- **Peat fires** 🟤 grow faster and send out more smoke.
- **Smoke drifts with the wind** 💨 (arrow in the top bar). Each puff that
  reaches a town costs one ❤️ of clean air (at most one per town every
  2.5 seconds); the haze visibly thickens as clean air runs out.
- **Gas flares** 🏭 are false alarms: tapping one costs 50 points.
- The wind changes direction and the game speeds up every 15 seconds
  (4 levels).
- **⏸ Pause** and **⏹ Stop** at any time; the game also pauses itself when
  you switch browser tab, and the P key toggles pause.
- End screen with score, fires put out, false alarms, best score (saved in
  this browser only), a rank (🌱 Junior Ranger, 🚒 Fire Fighter,
  🛰️ Haze Hunter, 🔥 Haze Hero) and a real fact about fires and haze.
- On narrow screens the map sits at the top with a quick icon key below.
- Practice game with made-up fires; it does not use the dashboard data.

## 📘 Guide

- How the attention score works (factor table).
- Data sources and how to add a real peat map and known heat sources.
- How to interpret results, about the project, and a data safety note.

## How the data is processed

1. **Loading** — demo CSV, uploaded CSV, or live NASA FIRMS (MODIS and VIIRS
   S-NPP, NOAA-20, NOAA-21). Field handling:
   - VIIRS confidence letters are converted to numbers (low 30, nominal 60,
     high 90).
   - The satellite is read from the FIRMS `instrument` column, or from
     satellite codes (Terra/Aqua/T/A = MODIS).
   - Column names are accepted in any capitalisation; acquisition date and
     time are combined into one timestamp.
   - Live detections are labelled with the nearest town.
   - Bad files give a readable error message instead of a crash.
2. **False-alarm filter** — flags detections that FIRMS marks as volcano,
   static industrial source or offshore (archive data), detections near
   places in `data/known_heat_sources.csv`, and places people reported as
   false alarms (1 km radius).
3. **MODIS/VIIRS matching** — pairs signals within the chosen time and
   distance, nearest pairs first; each signal is paired at most once. Only
   records inside each other's time window are compared, so thousands of
   detections are matched in a fraction of a second. Results are cached.
4. **Fire areas** — detections within the grouping distance (default 2 km)
   and up to 2 days apart are joined into one fire area. Each area records
   days detected (MYT), detections per satellite, whether both satellites
   agreed, spread direction and distance, and the nearest town.
5. **Peatland** — each detection is checked against a GeoJSON peat layer
   (`data/peatland.geojson` for real data; demo mode uses clearly labelled
   illustrative areas).
6. **Attention score (0-100)** — seen by both satellites 35, still burning
   after several days 25 (full at 3 days), on peatland 25, satellite
   confidence 15. Without a peat layer the other factors are scaled to 100.
   High is 70 or more, Medium 40 to 69, Low below 40.
7. **Smoke direction** — for the highlighted fire areas, the average 10 m
   wind over the next 24 hours (Open-Meteo forecast, no key needed) gives a
   straight-line drift of up to 300 km. Towns within 30 degrees of the drift
   direction and within reach, or within 15 km of the fire, are listed with an
   approximate arrival time. Demo mode uses an example south-west monsoon wind
   (12 km/h).
8. **Ground reports** — attach to fire areas within 2 km and 3 days of the
   report.

## Look and feel

- FireWatch colour theme (dark by default) in `.streamlit/config.toml`:
  teal buttons, sliders, selected items and score bars on a dark teal
  background. Users can still switch to the light theme from Streamlit's
  ⋮ → Settings.
- Charts follow the active theme instead of forcing a white background.
- Consistent colours: MODIS orange, VIIRS teal, matched pairs purple;
  attention High red, Medium orange, Low grey.
- English throughout. Bahasa Malaysia text for the summary and the game is
  kept in the code (`summary.py`, `scoring.py`, `game.py`) for a future full
  translation.

## Setup options

| Setting | Where | Purpose |
|---|---|---|
| `FIREWATCH_USERNAME`, `FIREWATCH_PASSWORD` | `.streamlit/secrets.toml` | Team login |
| `FIRMS_MAP_KEY` | `.streamlit/secrets.toml` | Live data and Past years |
| `FIREWATCH_FEEDBACK_PATH` | `.streamlit/secrets.toml` | Where ground reports are saved (default `data/feedback.csv`) |
| Peat map | `data/peatland.geojson` | Enables the peatland flag for live and uploaded data |
| Known heat sources | `data/known_heat_sources.csv` | Verified gas flares, factories and other non-fire heat |

## Testing

- 61 unit tests (pytest) covering data loading and FIRMS formats, matching
  (including a check that the fast matcher gives the same pairs as a
  compare-everything method, and a 6,000-record speed test), fire areas,
  peatland, scoring, smoke direction, the daily summary in both languages,
  ground reports, false-alarm filtering, the Haze Patrol page, the FIRMS live and history client
  (with simulated responses), filters, map features and login.
- GitHub Actions runs lint (flake8) and tests on every push and pull request.

## Known limitations

- Demo records are fictional. No real peatland map or known heat source list
  is bundled yet.
- Live NASA FIRMS loading is covered by tests with simulated responses but
  has not yet been run with a real `FIRMS_MAP_KEY`.
- The smoke outlook ignores terrain, rain and plume height; it is a screening
  aid, not an air-quality forecast.
- Ground reports are stored in a CSV file, which resets on Streamlit Cloud
  restarts unless `FIREWATCH_FEEDBACK_PATH` points to persistent storage.
- FIRMS only marks volcano/industrial/offshore detections in archive data,
  not in near-real-time data.
- Only one custom colour theme is possible in Streamlit 1.39; the light
  theme uses Streamlit's standard colours.
- Matching distance is an approximation suitable for regional distances, and
  nearest-pair selection is greedy rather than a global optimum.
- Satellite and confidence filters are applied before matching, so selecting
  only one satellite removes cross-satellite comparison.
- Some unusable uploaded rows are dropped during loading; there is no
  detailed rejected-row report yet.
- Coverage circles show the matching radius, not fire size, burned area,
  cause or intensity.
- A thermal anomaly is not confirmation of a fire, and the dashboard is not
  an emergency response or official verification tool.
