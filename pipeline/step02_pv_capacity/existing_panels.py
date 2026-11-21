"""Step 2b: find solar panels already on the roof, from the orthophoto + LiDAR (rules, no AI).

Why: we want to tell existing panels apart from room for new ones, and for the
validation on the CEP9 school we also want the opposite, to pretend the roof is
empty so our layout can be compared with the real one.

How (on the 0.1 m photo grid, inside the footprint):
1. Panel pixels are neutral grey or blue (red minus blue under NEUTRAL_MAX_WARMTH),
   neither black shadow nor white render, while the bare roof here is warm
   (gravel, tan membrane: red is 40-60 above blue).
2. Panels have texture: module frames and row gaps make the brightness vary
   over a few pixels. Smooth grey surfaces (concrete, render) do not.
3. Clean up: remove anything narrower than a panel (OPEN_PX), close the gaps
   between rows, and keep blobs of at least MIN_BLOB_M2.
4. LiDAR check: a panel blob sits on the roof, not on a wall. Blobs with less
   than MIN_ON_SURFACE of their area on a LiDAR roof surface (or on a cell
   that LiDAR marked as obstacle only because the panels stick up) are
   dropped. For each blob we also report the height ripple (rows of tilted
   panels show up as stripes 0.1-0.6 m high); flush glazing and very flat
   panels show none.

5. Things that look like panels but are not (solar water heaters, glazing) are listed
   by hand in not_panels.csv (refcat, x, y, radius_m, what). A blob whose centre
   is within radius_m of a listed point is not counted as a panel; it stays on the
   roof as an obstacle, also when the roof is treated as empty.

All thresholds are ASSUMPTIONS, tuned by eye on the two CEP9 roofs
(21 Nov 2026), where the photo shows dark grey modules on the Institut Quatre
Cantons roof and light-blue rows on the Escola Pere IV roof.
"""
import csv
from pathlib import Path

import numpy as np
from scipy import ndimage

NEUTRAL_MAX_WARMTH = 30   # red - blue below this = not the warm roof finish
MIN_BRIGHT, MAX_BRIGHT = 60, 235
NEUTRAL_SHARE = 0.6       # share of neutral pixels in a 0.9 m window
MIN_TEXTURE = 10          # mean local brightness std (0-255 scale) in a 0.9 m window
OPEN_PX = 7               # 0.7 m: thinner things (wall tops, edges) are removed; steep single panel rows are about 1 m wide
CLOSE_PX = 7              # 0.7 m: gaps between panel rows are closed
MIN_BLOB_M2 = 4.0         # about 1.5 panels
MIN_ON_SURFACE = 0.6      # share of a blob that must lie on LiDAR roof surface (or low raised cells)
RAISED_MAX_M = 1.5        # obstacle cells at most this high above the surface can be panel rows (steep rows on CEP9 reach about 1.2 m)
PANEL_COVER = 0.75        # ASSUMPTION: share of a panel block covered by panels (rest = row gaps)
NOT_PANELS_PATH = Path(__file__).resolve().parent / "not_panels.csv"


def load_not_panels(refcat, path=NOT_PANELS_PATH):
    """[(x, y, radius_m, what)] listed for this plot in not_panels.csv."""
    if not refcat or not Path(path).exists():
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [(float(r["x"]), float(r["y"]), float(r["radius_m"]), r["what"].strip())
                for r in csv.DictReader(f) if r["refcat"].strip()[:14].upper() == refcat[:14].upper()]


def _local_std(v, size):
    m = ndimage.uniform_filter(v, size)
    return np.sqrt(np.maximum(ndimage.uniform_filter(v * v, size) - m * m, 0))


def photo_candidates(rgb, roof):
    """Pixels that look like panels on the photo (bool, same shape as roof)."""
    rgb = rgb.astype(float)
    r, b = rgb[..., 0], rgb[..., 2]
    v = rgb.mean(axis=2)
    neutral = (r - b < NEUTRAL_MAX_WARMTH) & (v > MIN_BRIGHT) & (v < MAX_BRIGHT)
    texture = ndimage.uniform_filter(_local_std(v, 7), 9)
    m = roof & (ndimage.uniform_filter(neutral.astype(float), 9) > NEUTRAL_SHARE) & (texture > MIN_TEXTURE)
    m = ndimage.binary_opening(m, np.ones((OPEN_PX, OPEN_PX)))
    return ndimage.binary_closing(m, np.ones((CLOSE_PX, CLOSE_PX))) & roof


def detect(rgb, lroof, factor, not_panels=()):
    """Existing panels on one roof.

    rgb: photo on lroof.grid.finer(factor); lroof: step 02 LiDAR reading;
    not_panels: [(x, y, radius_m, what)] of look-alikes to leave out (load_not_panels).
    Returns (panel mask on the photo grid, panel mask on the LiDAR grid, list of panel
    blobs, mask on the LiDAR grid of the look-alikes, which stay obstacles).
    """
    from .grid import upsample

    roof_fine = upsample(lroof.roof, factor)
    cand = photo_candidates(rgb, roof_fine)
    surface = lroof.surface_id >= 0
    base = _surface_height(lroof)
    raised = lroof.obstacle & np.isfinite(lroof.dsm) & (lroof.dsm - base <= RAISED_MAX_M)
    ok_fine = upsample(surface | raised, factor)

    px_m2 = (lroof.grid.res / factor) ** 2
    lab, n = ndimage.label(cand)
    keep = np.zeros_like(cand)
    other = np.zeros_like(cand)
    blobs = []
    for k in range(1, n + 1):
        cells = lab == k
        area = cells.sum() * px_m2
        if area < MIN_BLOB_M2 or ok_fine[cells].mean() < MIN_ON_SURFACE:
            continue
        rows, cols = np.nonzero(cells)
        cx = lroof.grid.x0 + (cols.mean() + 0.5) * lroof.grid.res / factor
        cy = lroof.grid.y1 - (rows.mean() + 0.5) * lroof.grid.res / factor
        if any(np.hypot(cx - x, cy - y) <= r for x, y, r, _ in not_panels):
            other |= cells
            continue
        keep |= cells
        coarse = cells.reshape(lroof.roof.shape[0], factor, lroof.roof.shape[1], factor).mean(axis=(1, 3)) >= 0.5
        h = lroof.dsm[coarse & np.isfinite(lroof.dsm)]
        blobs.append({
            "area_m2": round(float(area), 1),
            "x": round(float(cx), 2),
            "y": round(float(cy), 2),
            "lidar_ripple_m": round(float(np.std(h - np.median(h))), 2) if h.size >= 4 else None,
        })
    shape = (lroof.roof.shape[0], factor, lroof.roof.shape[1], factor)
    coarse_keep = keep.reshape(shape).mean(axis=(1, 3)) >= 0.5
    coarse_other = other.reshape(shape).mean(axis=(1, 3)) > 0
    return keep, coarse_keep & lroof.roof, sorted(blobs, key=lambda b: -b["area_m2"]), coarse_other & lroof.roof


def _surface_height(lroof):
    """Height of the nearest roof surface for every cell (for 'how far does this stick up')."""
    surface = lroof.surface_id >= 0
    if not surface.any():
        return np.full(lroof.dsm.shape, np.nanmedian(lroof.dsm))
    _, (ri, ci) = ndimage.distance_transform_edt(~surface, return_indices=True)
    return lroof.dsm[ri, ci]


def summary(blobs, panel_m2):
    """Area and an estimated count of existing panels of panel_m2 each."""
    area = sum(b["area_m2"] for b in blobs)
    return {"existing_panels_m2": round(area, 1),
            "existing_panels_estimate": int(round(area * PANEL_COVER / panel_m2)),
            "existing_panels_estimate_note": f"block area x {PANEL_COVER} (ASSUMPTION: share covered by panels) / {panel_m2:.2f} m2 per panel",
            "existing_panel_blocks": blobs}
