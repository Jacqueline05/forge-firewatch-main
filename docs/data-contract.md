# Hotspot data contract

The harmonization engine expects one row per satellite observation.

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Unique source record identifier |
| `source` | enum | `MODIS` or `VIIRS` |
| `observed_at` | ISO timestamp | Observation time in UTC |
| `latitude` | decimal | Latitude from -90 to 90 |
| `longitude` | decimal | Longitude from -180 to 180 |
| `confidence` | integer | Source confidence score from 0 to 100 |
| `brightness` | decimal | Optional thermal brightness value |
| `region` | string | Human-readable study area |

## Matching rule

Two records are potential matches when:

1. Their sources are different.
2. Their observation times are within the configured time window.
3. Their approximate distance is within the configured geographic radius.

When several candidates qualify, the nearest available MODIS/VIIRS pairs are
selected first, and each observation belongs to at most one pair. The result
includes `matched_id` and `match_distance_km` for reviewing each pair.

On the map, a paired MODIS/VIIRS observation is drawn once at the midpoint.
Its coverage circle, like the circle for an unmatched observation, uses the
selected geographic threshold as its radius. The displayed diameter is twice
that value. These circles visualize the comparison radius; they are not
estimates of a fire's actual burned area.

Matches remain hypotheses for comparison and must not be presented as
confirmed fire identity.
