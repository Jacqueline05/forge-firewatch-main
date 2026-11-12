"""Check whether detections fall on peatland, using a GeoJSON polygon layer."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class PeatLayer:
    """Peatland polygons. Each polygon is a list of rings of (lon, lat)."""

    polygons: list[list[np.ndarray]] = field(default_factory=list)
    name: str = ""
    illustrative: bool = False

    @property
    def available(self) -> bool:
        return bool(self.polygons)


def load_peat_layer(path: str | Path, illustrative: bool = False) -> PeatLayer:
    """Load Polygon/MultiPolygon features from a GeoJSON file (WGS84)."""
    path = Path(path)
    if not path.exists():
        return PeatLayer()
    collection = json.loads(path.read_text(encoding="utf-8"))
    features = collection.get("features", [collection])
    polygons = []
    for feature in features:
        geometry = feature.get("geometry", feature)
        if geometry.get("type") == "Polygon":
            parts = [geometry["coordinates"]]
        elif geometry.get("type") == "MultiPolygon":
            parts = geometry["coordinates"]
        else:
            continue
        for rings in parts:
            polygons.append([np.asarray(ring, dtype=float)[:, :2] for ring in rings])
    name = collection.get("name", path.stem)
    return PeatLayer(polygons=polygons, name=name, illustrative=illustrative)


def _inside_ring(lon: np.ndarray, lat: np.ndarray, ring: np.ndarray) -> np.ndarray:
    """Even-odd ray casting for many points against one ring."""
    inside = np.zeros(len(lon), dtype=bool)
    x1, y1 = ring[:-1, 0], ring[:-1, 1]
    x2, y2 = ring[1:, 0], ring[1:, 1]
    for ax, ay, bx, by in zip(x1, y1, x2, y2):
        crosses = (ay > lat) != (by > lat)
        if not crosses.any():
            continue
        with np.errstate(divide="ignore", invalid="ignore"):
            x_at = ax + (lat - ay) * (bx - ax) / (by - ay)
        inside ^= crosses & (lon < x_at)
    return inside


def points_on_peat(latitudes, longitudes, layer: PeatLayer) -> np.ndarray:
    """Return a boolean array: True where a point lies on a peat polygon."""
    lat = np.asarray(latitudes, dtype=float)
    lon = np.asarray(longitudes, dtype=float)
    result = np.zeros(len(lat), dtype=bool)
    for rings in layer.polygons:
        outer = rings[0]
        box = (
            (lon >= outer[:, 0].min()) & (lon <= outer[:, 0].max())
            & (lat >= outer[:, 1].min()) & (lat <= outer[:, 1].max())
        )
        if not box.any():
            continue
        candidates = np.flatnonzero(box)
        inside = np.zeros(len(candidates), dtype=bool)
        for ring in rings:  # outer ring plus any holes (even-odd rule)
            inside ^= _inside_ring(lon[candidates], lat[candidates], ring)
        result[candidates] |= inside
    return result
