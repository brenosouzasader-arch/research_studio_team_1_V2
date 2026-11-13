"""Pipeline step 2: read the roof with LiDAR. Address in, usable m2 + obstacle map out.

    python -m step02_pv_capacity.read_roof "Carrer de Jordi Girona 29, Barcelona" --laz-dir data/lidar --out nexus2

LiDAR rules only. V1 also had an AI photo model (U-Net) here; it was left out of V2
because the midterm reviewers said this step does not need AI. It is still in the V1
repository (pipeline/step2/model.py, train.py, dataset.py) if we want it back.

Writes <out>.json (numbers), <out>_usable.geojson (usable area, EPSG:25831),
<out>_preview.png (photo with the reading on top), <out>_photo.png (the plain
roof photo) and <out>_height.png (LiDAR height above the main roof level).
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from shapely.geometry import mapping

from step01_select_host.find_building import find_building

from . import ortho
from .grid import upsample
from .lidar_roof import read_roof_from_tiles

MIN_LIDAR_COVERAGE = 0.9  # share of roof cells with LiDAR points
FACTOR = 5                # 0.5 m LiDAR cell = 5 x 5 photo pixels at 0.1 m
CLASSES = ["outside", "free_roof", "obstacle", "solar_panel"]
COLORS = [(0, 0, 0), (60, 180, 75), (230, 25, 75), (0, 130, 200)]
UNSURE = (255, 255, 255)


def height_above_roof(lroof):
    """LiDAR heights relative to the largest roof surface (metres)."""
    if lroof.summary["surfaces"]:
        base = lroof.summary["surfaces"][0]["height_m"]
    else:
        base = np.nanmedian(lroof.dsm) if np.isfinite(lroof.dsm).any() else 0.0
    return lroof.dsm - base


def lidar_classes(lroof):
    """Class number per 0.5 m cell from LiDAR (0 outside, 1 free roof, 2 obstacle)."""
    out = np.zeros(lroof.roof.shape, dtype=np.uint8)
    out[lroof.surface_id >= 0] = CLASSES.index("free_roof")
    out[lroof.obstacle] = CLASSES.index("obstacle")
    return out


def classes_to_colors(classes):
    out = np.zeros(classes.shape + (3,), dtype=np.uint8)
    for k, col in enumerate(COLORS):
        out[classes == k] = col
    return out


def lidar_only(lroof):
    s = lroof.summary
    coverage_ok = s["lidar_coverage"] >= MIN_LIDAR_COVERAGE
    summary = {
        "method": "lidar only",
        "usable_area_m2": s["usable_area_m2"],
        "free_area_m2": s["free_area_m2"],
        "obstacle_area_m2": s["obstacle_area_m2"],
        "existing_panels_m2": None,  # LiDAR can't tell panels from roof
        "confidence": "medium" if coverage_ok else "low",
        "lower_roof_m2": s.get("lower_roof_m2"),
        "excluded": s.get("excluded"),
    }
    return summary, lroof.usable, None, lroof.grid


USABLE_COLOR = (255, 230, 0)   # yellow outline: where panels fit
# height colours from 1 m below to 5 m above the main roof: blue, green, yellow, red
HEIGHT_STOPS = np.array([-1.0, 0.0, 1.0, 2.5, 5.0])
HEIGHT_COLORS = np.array([(40, 70, 160), (60, 180, 75), (180, 210, 60), (250, 200, 40), (215, 40, 40)])


def _edge(mask):
    return mask & ~ndimage.binary_erosion(mask)


def preview(rgb, classes, roof, usable, path, alpha=0.45):
    """Photo + class colours on the roof, roof outline in white, usable area outlined in yellow."""
    overlay = classes_to_colors(classes).astype(np.float32)
    base = rgb.astype(np.float32) if rgb is not None else np.full(overlay.shape, 128.0)
    out = base.copy()
    out[roof] = (1 - alpha) * base[roof] + alpha * overlay[roof]
    out[_edge(roof)] = 255
    out[_edge(usable)] = USABLE_COLOR
    Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(path)


def height_image(height, roof, path):
    """LiDAR height above the main roof level as colours; outside the roof is grey."""
    out = np.full(height.shape + (3,), 200, dtype=np.float32)
    ok = roof & np.isfinite(height)
    h = np.clip(height[ok], HEIGHT_STOPS[0], HEIGHT_STOPS[-1])
    for ch in range(3):
        out[..., ch][ok] = np.interp(h, HEIGHT_STOPS, HEIGHT_COLORS[:, ch])
    out[_edge(roof)] = 0
    Image.fromarray(out.astype(np.uint8)).save(path)


def read_roof(laz_dir, address=None, lat=None, lon=None, out="roof"):
    record, fp = find_building(address, lat, lon)
    lroof = read_roof_from_tiles(fp, laz_dir, refcat=record.refcat)
    if lroof is None:
        raise SystemExit("No LiDAR tile in --laz-dir covers this building. Download the tile first.")
    fine = lroof.grid.finer(FACTOR)

    rgb, photo_error = None, None
    try:
        rgb = ortho.get_ortho(fine)
    except Exception as e:  # the LiDAR reading still works without the photo
        photo_error = str(e)[:200]

    summary, usable, _, grid = lidar_only(lroof)
    classes = upsample(lidar_classes(lroof), FACTOR)

    result = {
        "building": {"refcat": record.refcat, "address": record.catastro_address,
                     "query": record.query, "year_built": record.year_built,
                     "dwellings": record.dwellings},
        "roof": summary,
        "lidar": lroof.summary,
        "photo_error": photo_error,
    }
    Path(f"{out}.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    poly = grid.cells_to_polygon(usable)
    fc = {"type": "FeatureCollection",
          "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::25831"}},
          "features": [] if poly is None else [{"type": "Feature", "geometry": mapping(poly),
                                               "properties": {"usable_area_m2": summary["usable_area_m2"]}}]}
    Path(f"{out}_usable.geojson").write_text(json.dumps(fc), encoding="utf-8")
    roof_fine = upsample(lroof.roof, FACTOR)
    preview(rgb, classes, roof_fine, upsample(usable, FACTOR), f"{out}_preview.png")
    if rgb is not None:
        Image.fromarray(rgb).save(f"{out}_photo.png")
    height_image(upsample(height_above_roof(lroof), FACTOR), roof_fine, f"{out}_height.png")
    return result


def main():
    ap = argparse.ArgumentParser(description="Pipeline step 2: read the roof (LiDAR)")
    ap.add_argument("address", nargs="?")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--laz-dir", required=True, help="folder with ICGC/CNIG LAZ tiles")
    ap.add_argument("--out", default="roof", help="output name, without extension")
    args = ap.parse_args()
    if not args.address and (args.lat is None or args.lon is None):
        ap.error("give an address, or both --lat and --lon")
    result = read_roof(args.laz_dir, args.address, args.lat, args.lon, args.out)
    print(json.dumps({k: result.get(k) for k in ("building", "roof", "photo_error")}, indent=2, default=str))


if __name__ == "__main__":
    main()
