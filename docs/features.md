# Borneo FireWatch features

This document describes features implemented in the current MVP. The project
uses fictional demonstration records by default and is not yet connected to a
live NASA FIRMS feed.

## Dashboard and access

- Streamlit dashboard with **Overview**, **Explore signals**, and
  **Guide and methodology** sections.
- Team login and sign-out using credentials configured through Streamlit
  secrets.
- Introductory guidance explaining what the map and observations represent.

## Data input and filters

- Loads the built-in sample dataset at `data/sample_hotspots.csv`.
- Accepts CSV uploads using the project data schema and selected common NASA
  FIRMS fields.
- Normalizes supported satellite, acquisition date/time, and confidence
  fields into the project schema.
- Filters observations by satellite source and minimum confidence.
- Lets users set a time matching window from 5 to 120 minutes and a geographic
  matching distance from 1 to 25 km.

## MODIS and VIIRS comparison

- Validates required observation fields, satellite source values, and
  coordinate ranges.
- Compares MODIS and VIIRS records using an approximate geographic distance
  and the selected time and distance thresholds.
- Pairs each observation with at most one observation from the other satellite.
  The nearest available candidate pairs are selected first.
- Labels observations as **matched**, **MODIS only**, or **VIIRS only**.
- Includes the paired record ID and measured separation distance in results.

## Maps and visualizations

- Interactive map with satellite-specific colors and confidence in marker
  hover details.
- Matched pairs appear once at the midpoint between their observations.
- Individual-signal map draws a coverage circle using the selected matching
  distance as its radius. The circle is a comparison aid, not a fire boundary
  or estimate of burned area.
- Individual-signal map includes a date timeline when the data has multiple
  observation dates.
- Signal-concentration map highlights areas with higher-confidence signals.
- Overview metrics include signal count, matched-pair count, agreement rate,
  represented regions, and a basic data-quality score.
- Analysis charts show daily observations, confidence by source, regional
  activity by source, and match-status distribution.

## Results

- Displays a harmonization table with observation IDs, satellite, time,
  region, confidence, match status, paired ID, and pair separation.
- Allows filtered harmonization results to be downloaded as a CSV file.
- Includes unit tests for harmonization, matching, map features, coverage
  circles, and authentication.

## Known limitations

- Default sample records are fictional; live FIRMS retrieval and API
  integration are not implemented.
- Matching distance is an approximation suitable for the MVP's regional
  distances. The nearest-available-pair selection is greedy, not a global
  optimal assignment.
- Satellite and confidence filters are applied before matching. Selecting
  only one satellite therefore removes the other source from cross-satellite
  comparison.
- Some unusable uploaded rows are dropped during CSV normalization; the app
  does not yet provide a detailed rejected-row report.
- The displayed coverage circles visualize the matching radius. They do not
  show actual fire size, burned area, cause, or intensity.
- A thermal anomaly is not confirmation of a fire and the dashboard is not an
  emergency response or official verification tool.
