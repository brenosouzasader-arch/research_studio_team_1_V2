"""LiDAR: which tiles cover the building, and is its roof flat?

Works on LAZ/LAS files you have downloaded from the ICGC (Territorial LiDAR,
3rd coverage) or CNIG (PNOA LiDAR) download viewers into one folder. Tiles are
matched by reading each file's header bounds, so the file names don't matter.
Both providers deliver EPSG:25831 for Catalonia, the same as Catastro.
"""
from pathlib import Path

import laspy
import numpy as np
import shapely
from shapely.geometry import box

BUILDING_CLASS = 6        # ASPRS class for building points
GRID_SIZE = 0.5           # metres per cell when rasterising the roof
FLAT_SLOPE_DEG = 5.0      # a cell counts as flat below this slope
FLAT_SHARE_NEEDED = 0.3   # ASSUMPTION (relaxed from 0.7 on Breno's decision, 15 Nov 2026): roof counts as flat if this share of cells is flat
MIN_POINTS = 50
UNCLASSIFIED = 1          # ASPRS class for points nobody classified
_warned = set()


def class_mask(las, classes, path=None):
    """True for points in `classes`.

    Some ICGC Territorial LiDAR sheets (3rd coverage) have no building class at
    all: roofs are left as class 1, "unclassified". Sheet 433584 in Poblenou is
    one (checked 15 Nov 2026: 0 class-6 points, the school roof is class 1 at
    about 14 m). If a sheet has no class-6 point, we treat its class-1 points as
    building, so half a roof is not lost at a sheet edge.
    """
    c = np.asarray(las.classification)
    classes = tuple(classes)
    if BUILDING_CLASS in classes and not (c == BUILDING_CLASS).any():
        classes += (UNCLASSIFIED,)
        name = getattr(path, "name", path)
        if name not in _warned:
            _warned.add(name)
            print(f"note: {name} has no building class; using its unclassified points as building")
    return np.isin(c, classes)


def tile_bounds(path):
    with laspy.open(path) as f:
        h = f.header
        return box(h.mins[0], h.mins[1], h.maxs[0], h.maxs[1])


def find_tiles(footprint, laz_dir):
    """Return paths of LAZ/LAS files in laz_dir whose extent overlaps the footprint."""
    hits = []
    for path in sorted(Path(laz_dir).glob("*.la[sz]")):
        try:
            if tile_bounds(path).intersects(footprint):
                hits.append(path)
        except Exception as e:  # unreadable file: skip, but say so
            print(f"warning: could not read {path.name}: {e}")
    return hits


def roof_points(footprint, tiles):
    """Building-class points (x, y, z) that fall inside the footprint."""
    chunks = []
    minx, miny, maxx, maxy = footprint.bounds
    for path in tiles:
        las = laspy.read(path)
        x, y, z = np.asarray(las.x), np.asarray(las.y), np.asarray(las.z)
        keep = class_mask(las, (BUILDING_CLASS,), path)
        keep &= (x >= minx) & (x <= maxx) & (y >= miny) & (y <= maxy)
        x, y, z = x[keep], y[keep], z[keep]
        inside = shapely.contains_xy(footprint, x, y)
        chunks.append(np.column_stack([x[inside], y[inside], z[inside]]))
    return np.vstack(chunks) if chunks else np.empty((0, 3))


def roof_flatness(points, grid=GRID_SIZE):
    """Rasterise the roof (highest point per cell) and measure how much of it is flat.

    Returns a dict with the share of flat cells, median slope and roof height
    range. Stair housings and tanks show up as small steep patches, so a flat
    roof with obstacles still scores high; a pitched roof scores low.
    """
    if len(points) < MIN_POINTS:
        return {"is_flat": None, "flat_share": None, "median_slope_deg": None,
                "roof_height_min": None, "roof_height_max": None,
                "points": int(len(points)), "note": "too few building points"}
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    ix = ((x - x.min()) / grid).astype(int)
    iy = ((y - y.min()) / grid).astype(int)
    dsm = np.full((iy.max() + 1, ix.max() + 1), np.nan)
    order = np.argsort(z)  # write lowest first so the highest point wins
    dsm[iy[order], ix[order]] = z[order]

    gy, gx = np.gradient(dsm, grid)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    valid = slope[~np.isnan(slope)]
    if valid.size == 0:
        flat_share = None
    else:
        flat_share = float((valid < FLAT_SLOPE_DEG).mean())
    return {
        "is_flat": None if flat_share is None else flat_share >= FLAT_SHARE_NEEDED,
        "flat_share": None if flat_share is None else round(flat_share, 3),
        "median_slope_deg": None if valid.size == 0 else round(float(np.median(valid)), 1),
        "roof_height_min": round(float(np.nanmin(dsm)), 2),
        "roof_height_max": round(float(np.nanmax(dsm)), 2),
        "points": int(len(points)),
        "note": None,
    }


# ---------- fallback footprint when Catastro has no building ----------

GROUND_CLASS = 2
TRACE_MIN_HEIGHT_M = 6.0  # ASSUMPTION: points this far above ground count as the main building (drops walls, canopies, low sheds)
TRACE_CELL_M = 1.0
TRACE_MIN_AREA_M2 = 30.0


def footprint_from_lidar(plot, point, tiles, min_height=TRACE_MIN_HEIGHT_M):
    """Trace a building outline from LiDAR inside a cadastral plot.

    Used only when Catastro has the plot but no building on it. Takes the
    building/unclassified points more than `min_height` above the plot's ground,
    grids them at 1 m, closes small gaps, and keeps the part that contains (or is
    nearest to) `point`. Returns (footprint, ground_z) or (None, None).
    """
    minx, miny, maxx, maxy = plot.bounds
    xs, ys, zs, cs = [], [], [], []
    for path in tiles:
        las = laspy.read(path)
        x, y = np.asarray(las.x), np.asarray(las.y)
        k = np.flatnonzero((x >= minx) & (x <= maxx) & (y >= miny) & (y <= maxy))
        k = k[shapely.contains_xy(plot, x[k], y[k])]
        cls = np.asarray(las.classification)[k]
        building = class_mask(las, (BUILDING_CLASS,), path)[k]
        xs.append(x[k]); ys.append(y[k]); zs.append(np.asarray(las.z)[k])
        cs.append(np.where(building, BUILDING_CLASS, cls))
    if not xs:
        return None, None
    x, y, z, c = (np.concatenate(a) for a in (xs, ys, zs, cs))
    if len(z) < MIN_POINTS:
        return None, None
    ground = z[c == GROUND_CLASS]
    ground_z = float(np.median(ground)) if ground.size else float(np.percentile(z, 5))
    high = (c == BUILDING_CLASS) & (z > ground_z + min_height)
    cells = set(zip(np.floor(x[high] / TRACE_CELL_M).astype(int), np.floor(y[high] / TRACE_CELL_M).astype(int)))
    if not cells:
        return None, ground_z
    s = TRACE_CELL_M
    shape = shapely.union_all([box(i * s, j * s, (i + 1) * s, (j + 1) * s) for i, j in cells])
    shape = shape.buffer(1).buffer(-1.5).buffer(0.5).intersection(plot)  # close gaps, drop thin strips
    parts = [g for g in getattr(shape, "geoms", [shape]) if g.area >= TRACE_MIN_AREA_M2]
    if not parts:
        return None, ground_z
    best = min(parts, key=lambda g: g.distance(point))
    return best.simplify(0.5), ground_z
