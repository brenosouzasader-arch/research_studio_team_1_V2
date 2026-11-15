"""Step 3: place tilted panel rows on the usable roof area.

Flat Barcelona roofs usually get low-tilt rows on a frame. Rows run along the
building edge whose outward direction is closest to south (in the Eixample's
45-degree grid that means south-east or south-west), because rows squared to
the building fill far more of the roof than rows turned to true south, and at
10 degrees of tilt the yield difference is only a few percent.

Rows are spaced so the row in front does not shade the next one when the sun
is at WINTER_NOON_ELEVATION_DEG. Several grid shifts are tried and the one
that fits the most panels is kept.
"""
import math
from dataclasses import dataclass

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import box

PANEL_LONG_M = 1.76        # along the row
PANEL_SHORT_M = 1.13       # up the slope (landscape)
PANEL_WP = 420             # peak watts per panel (about 21% efficient)
TILT_DEG = 10.0
GAP_M = 0.05               # between panels in a row
WINTER_NOON_ELEVATION_DEG = 25.0  # Barcelona, 21 December at noon
SHIFT_STEP_M = 0.25


@dataclass(frozen=True)
class Module:
    """One panel model: peak watts and size. Both sizes are ASSUMPTIONS (typical
    catalogue panels), listed in docs/SOURCES.md."""
    wp: int
    long_m: float          # along the row
    short_m: float         # up the slope (landscape)
    label: str


MODULES = {
    # Our default since V1: a 108-cell panel of about 21% efficiency.
    420: Module(420, PANEL_LONG_M, PANEL_SHORT_M, "420 W, 1.76 x 1.13 m (default)"),
    # The CEP9 school's system works out at 540 W a panel (58.32 kWp / 108 panels).
    # A typical 540 W panel (144 half-cells) is about 2.28 x 1.13 m.
    540: Module(540, 2.28, 1.13, "540 W, 2.28 x 1.13 m (as on the CEP9 school)"),
}
DEFAULT_MODULE = MODULES[PANEL_WP]


def get_module(wp):
    """The Module for a wattage in MODULES (420 or 540)."""
    try:
        return MODULES[int(wp)]
    except (KeyError, ValueError):
        raise SystemExit(f"unknown panel wattage {wp}; choose from {sorted(MODULES)}")


@dataclass
class Layout:
    panels: list           # shapely polygons (footprint on the roof, EPSG:25831)
    azimuth_deg: float     # direction the panels face, from north, clockwise
    tilt_deg: float
    module: Module = DEFAULT_MODULE
    cells: list = None     # (row, column) of each panel in the layout grid; rows run along the building
    orientation_table: list = None   # what --orient search tried: azimuth, panels, yield factor, score

    @property
    def count(self):
        return len(self.panels)

    @property
    def kwp(self):
        return self.count * self.module.wp / 1000

    def subset(self, keep):
        """A new Layout with only the panels where keep is True."""
        cells = None if self.cells is None else [c for c, k in zip(self.cells, keep) if k]
        return Layout([p for p, k in zip(self.panels, keep) if k], self.azimuth_deg, self.tilt_deg,
                      self.module, cells, self.orientation_table)

    def centres(self):
        return np.array([[p.centroid.x, p.centroid.y] for p in self.panels]).reshape(-1, 2)


def facing_azimuth(footprint):
    """Of the directions square to the building's longest edge, the one closest to south."""
    ring = np.asarray(footprint.minimum_rotated_rectangle.exterior.coords)
    edges = np.diff(ring, axis=0)
    dx, dy = edges[np.argmax(np.hypot(edges[:, 0], edges[:, 1]))]
    edge_az = math.degrees(math.atan2(dx, dy)) % 360          # azimuth of the edge itself
    candidates = [(edge_az + k * 90) % 360 for k in range(4)]
    return min(candidates, key=lambda a: abs(((a - 180) + 180) % 360 - 180))


def row_pitch(tilt_deg=TILT_DEG, winter_elevation_deg=WINTER_NOON_ELEVATION_DEG, short_m=PANEL_SHORT_M):
    """Distance from one row to the next, measured on the roof (metres)."""
    t = math.radians(tilt_deg)
    depth = short_m * math.cos(t)
    rise = short_m * math.sin(t)
    return depth + rise / math.tan(math.radians(winter_elevation_deg))


def lay_out(usable, footprint, tilt_deg=TILT_DEG, azimuth_deg=None, module=DEFAULT_MODULE):
    """usable: shapely (multi)polygon of usable roof (EPSG:25831). Returns a Layout."""
    if usable is None or usable.is_empty:
        return Layout([], azimuth_deg or 180.0, tilt_deg, module, [])
    az = facing_azimuth(footprint) if azimuth_deg is None else azimuth_deg
    # work in a frame where panels face "down" (south = -v): rotate by (az - 180)
    centre = footprint.centroid
    rot = az - 180.0
    local = affinity.rotate(usable, rot, origin=centre)
    minx, miny, maxx, maxy = local.bounds
    long_m = module.long_m
    depth = module.short_m * math.cos(math.radians(tilt_deg))
    pitch_v = row_pitch(tilt_deg, short_m=module.short_m)
    pitch_u = long_m + GAP_M
    shapely.prepare(local)

    best, best_cells = [], []
    for du in np.arange(0, pitch_u, SHIFT_STEP_M):
        for dv in np.arange(0, pitch_v, SHIFT_STEP_M):
            us = np.arange(minx + du, maxx - long_m + 1e-6, pitch_u)
            vs = np.arange(miny + dv, maxy - depth + 1e-6, pitch_v)
            rects = [box(u, v, u + long_m, v + depth) for v in vs for u in us]
            cells = [(j, i) for j in range(len(vs)) for i in range(len(us))]
            if not rects:
                continue
            ok = shapely.contains(local, rects)
            fits = [r for r, k in zip(rects, ok) if k]
            if len(fits) > len(best):
                best = fits
                best_cells = [c for c, k in zip(cells, ok) if k]
    panels = [affinity.rotate(p, -rot, origin=centre) for p in best]
    return Layout(panels, az, tilt_deg, module, best_cells)


ORIENT_SPAN_DEG = 45       # --orient search tries the building's axis +/- this much, in steps of ORIENT_STEP_DEG
ORIENT_STEP_DEG = 5


def yield_factor(azimuth_deg, tilt_deg=TILT_DEG):
    """Rough share of the best-orientation (due south) yearly sun a panel gets when it faces
    azimuth_deg. ASSUMPTION: loss = 0.5 x sin(tilt) x (1 - cos(angle away from south)); at 10 degrees of
    tilt and 45 degrees off south that is 2.5%. It only ranks orientations here; the real yield
    comes from step 03's hour-by-hour model once an orientation is chosen."""
    off = math.radians(((azimuth_deg - 180) + 180) % 360 - 180)
    return 1 - 0.5 * math.sin(math.radians(tilt_deg)) * (1 - math.cos(off))


def orientation_table(usable, footprint, tilt_deg=TILT_DEG, module=DEFAULT_MODULE,
                      span=ORIENT_SPAN_DEG, step=ORIENT_STEP_DEG):
    """Lay the panels out at several orientations around the building's own axis (and due south) and
    score each by panels x yield factor. Rows turned a few degrees can fit more panels, but panels
    turned away from south make less, so the score weighs both. Returns the table, best first."""
    base = facing_azimuth(footprint)
    azs = {round((base + off) % 360, 1): off for off in range(-span, span + 1, step)}
    azs.setdefault(180.0, round(180.0 - base))
    rows = []
    for az, off in sorted(azs.items(), key=lambda kv: kv[1]):
        lay = lay_out(usable, footprint, tilt_deg, az, module)
        f = yield_factor(az, tilt_deg)
        rows.append({"azimuth_deg": az, "offset_from_building_deg": off, "panels": lay.count,
                     "yield_factor": round(f, 4), "score": round(lay.count * f, 1),
                     "is_building_axis": off == 0, "is_south": az == 180.0})
    return sorted(rows, key=lambda r: -r["score"])


def lay_out_oriented(usable, footprint, mode="building", tilt_deg=TILT_DEG, module=DEFAULT_MODULE):
    """mode: 'building' = rows along the building edge nearest south (the default since V1),
    'south' = rows facing due south, 'search' = the best of orientation_table()."""
    if mode == "building":
        return lay_out(usable, footprint, tilt_deg, None, module)
    if mode == "south":
        return lay_out(usable, footprint, tilt_deg, 180.0, module)
    if mode != "search":
        raise SystemExit(f"unknown orientation {mode}; choose building, south or search")
    if usable is None or usable.is_empty:
        return lay_out(usable, footprint, tilt_deg, None, module)
    table = orientation_table(usable, footprint, tilt_deg, module)
    lay = lay_out(usable, footprint, tilt_deg, table[0]["azimuth_deg"], module)
    lay.orientation_table = table
    return lay
