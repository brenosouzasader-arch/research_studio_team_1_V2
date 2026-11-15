"""Pipeline steps 3 and 4: lay out panels, then shade and yield. Address in, hourly kWh out.

    python -m step03_simulate_generation.shade_yield "Carrer de Roger de Llúria 56, Barcelona" --laz-dir data\\lidar --out lluria56
    python -m step03_simulate_generation.shade_yield "..." --laz-dir data\\lidar --usable lluria56_usable.geojson --out lluria56

Without --usable it reads the roof with step 2's LiDAR rules. With --usable it
uses a step 2 result you already have (for example one read with the AI model).

Writes <out>_yield.json (totals, monthly kWh, every panel), <out>_hourly.csv
(8760 hours of AC kWh for the whole roof, for step 5 and energy sharing),
<out>_panels.geojson (panel outlines, EPSG:25831) and <out>_panels.png. Without
--usable it also writes <out>_usable.geojson (the usable roof it found).
The hourly CSV is what step 04 (host table) reads.

Panels: by default every panel that fits (team decision: fill the roof). To try a smaller
system after seeing the money in step 08, run again with --max-panels N; the N panels that
produce most are kept.

Layout options (see options.py): every run also works out three layouts, "max" (fill the
roof), "neat" (neat blocks of good panels) and "best" (bigger blocks of the best panels),
for each panel wattage in --compare-wp (default 420 and 540 W). They are listed under
"variants" in <out>_yield.json, each with its own <out>_hourly_<W>_<option>.csv, and drawn
side by side in <out>_options.png. --panel-wp and --layout choose which one the main
outputs (<out>_hourly.csv, <out>_panels.*) and the later steps use.
"""
import argparse
import csv
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from step01_select_host.find_building import find_building
from step02_pv_capacity.lidar_roof import read_roof_from_tiles
from step02_pv_capacity.read_roof import lidar_only
from step02_pv_capacity.layout import DEFAULT_MODULE, MODULES, Layout, Module, get_module, lay_out_oriented

from .energy import yield_for_layout
from .horizon import horizons, surface_model
from .options import OPTIONS, all_options
from .weather import DEFAULT_PATH, load_tmy

MOUNT_HEIGHT_M = 0.4   # panel centre above the roof surface
MAX_SHADE_LOSS = 0.4   # drop panels that lose more than this share of their sun to shade


def panel_heights(lroof, centres):
    """Roof surface height under each panel centre, plus the mounting height."""
    row, col = lroof.grid.rowcol(centres[:, 0], centres[:, 1])
    row = row.clip(0, lroof.grid.height - 1)
    col = col.clip(0, lroof.grid.width - 1)
    z = lroof.dsm[row, col]
    fallback = np.nanmedian(lroof.dsm) if np.isfinite(lroof.dsm).any() else 0.0
    return np.where(np.isfinite(z), z, fallback) + MOUNT_HEIGHT_M


def load_usable(path):
    fc = json.loads(Path(path).read_text(encoding="utf-8"))
    geoms = [shape(f["geometry"]) for f in fc.get("features", [])]
    return unary_union(geoms) if geoms else None


def roof_summary(lroof, usable, usable_path):
    """Step 2 numbers for the map: from the step 2 run that made --usable (it may have used
    the AI model), otherwise from the LiDAR reading done here."""
    if usable_path:
        step2_json = Path(str(usable_path).replace("_usable.geojson", ".json"))
        if step2_json.exists() and step2_json != Path(usable_path):
            return json.loads(step2_json.read_text(encoding="utf-8"))["roof"]
        return {**lidar_only(lroof)[0], "method": "usable area given",
                "usable_area_m2": round(usable.area, 1) if usable is not None else 0.0}
    return lidar_only(lroof)[0]


def usable_geojson(usable):
    return {"type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::25831"}},
            "features": [] if usable is None or usable.is_empty else
            [{"type": "Feature", "geometry": mapping(usable),
              "properties": {"usable_area_m2": round(usable.area, 1)}}]}


def analyse(lroof, footprint, laz_dir, weather, lat, lon, usable=None, max_shade_loss=MAX_SHADE_LOSS,
            max_panels=None, module=DEFAULT_MODULE, surface=None, orient="building"):
    """Steps 3 + 4 for one roof and one panel model. Returns (kept layout, yearly kWh
    per kept panel, shade loss per kept panel, hourly kWh of the kept panels, dropped
    panels, hourly kWh of each kept panel as an (n_panels, n_hours) array).
    surface: (grid, dsm) from surface_model, to reuse it across panel models."""
    if usable is None:
        usable = lroof.grid.cells_to_polygon(lroof.usable)
    layout = lay_out_oriented(usable, footprint, orient, module=module)
    if not layout.count:
        return layout, np.zeros(0), np.zeros(0), np.zeros(len(weather)), [], np.zeros((0, len(weather)))
    grid, dsm = surface if surface is not None else surface_model(footprint, laz_dir)
    centres = layout.centres()
    horizon = horizons(grid, dsm, centres[:, 0], centres[:, 1], panel_heights(lroof, centres))
    kwh, loss, hourly, keep, per_panel = yield_for_layout(layout, horizon, weather, lat, lon,
                                                          max_shade_loss, max_panels, per_panel=True)
    dropped = [p for p, k in zip(layout.panels, keep) if not k]
    return layout.subset(keep), kwh[keep], loss[keep], hourly, dropped, per_panel[keep]


def variants_for(layout, kwh, per_panel, weather):
    """The three layout options (options.py) for one analysed layout.
    Returns a list of (option dict, keep mask, number of blocks, hourly kWh, weak mask).
    The block areas are judged with this panel model's size, so a 540 W panel needs fewer panels."""
    cells = layout.cells if layout.cells is not None else [(0, i) for i in range(layout.count)]
    chosen = all_options(cells, kwh, layout.module.long_m * layout.module.short_m)
    out = []
    for o in OPTIONS:
        keep, n_blocks, weak = chosen[o["id"]]
        hourly = per_panel[keep].sum(axis=0) if keep.any() else np.zeros(len(weather))
        out.append((o, keep, n_blocks, hourly, weak))
    return out


def left_out(layout, keep, weak):
    """Panels the option does not keep, with the reason: 'weak' (below its cut-off) or 'loose'
    (good, but not inside a big enough block). For the website to draw them."""
    return [{"c": corners(p), "why": "weak" if w else "loose"}
            for p, k, w in zip(layout.panels, keep, weak) if not k]


def corners(p):
    return [[round(x, 2), round(y, 2)] for x, y in list(p.exterior.coords)[:4]]


def summarise(layout, kwh, loss, hourly, weather):
    months = weather.times.astype("datetime64[M]").astype(int) % 12
    total = float(kwh.sum())
    return {
        "panels": layout.count,
        "kwp": round(layout.kwp, 2),
        "tilt_deg": layout.tilt_deg,
        "azimuth_deg": round(layout.azimuth_deg, 1),
        "yearly_kwh": round(total),
        "kwh_per_kwp": round(total / layout.kwp) if layout.count else None,
        "mean_shade_loss": round(float(loss.mean()), 3) if layout.count else None,
        "monthly_kwh": [round(float(hourly[months == m].sum())) for m in range(12)],
        "peak_hour_kw": round(float(hourly.max()), 2),
    }


def panels_png(footprint, usable, layout, kwh, path, dropped=(), px_per_m=10, scale=None):
    minx, miny, maxx, maxy = footprint.buffer(2).bounds
    w, h = int((maxx - minx) * px_per_m), int((maxy - miny) * px_per_m)
    img = Image.new("RGB", (w, h), (235, 232, 226))
    d = ImageDraw.Draw(img)
    T = lambda xy: [((x - minx) * px_per_m, (maxy - y) * px_per_m) for x, y in xy]
    for g in getattr(usable, "geoms", [usable]) if usable is not None else []:
        d.polygon(T(g.exterior.coords), fill=(255, 240, 150))
        for hole in g.interiors:
            d.polygon(T(hole.coords), fill=(235, 232, 226))
    for g in getattr(footprint, "geoms", [footprint]):
        d.polygon(T(g.exterior.coords), outline=(60, 60, 60))
    for p in dropped:
        d.polygon(T(p.exterior.coords), fill=(200, 200, 200), outline=(150, 150, 150))
    lo, hi = scale if scale else ((kwh.min(), kwh.max()) if len(kwh) else (0, 1))
    for p, k in zip(layout.panels, kwh):
        t = 0.0 if hi <= lo else (k - lo) / (hi - lo)   # dark blue = most shade, orange = best
        colour = tuple(int(a + (b - a) * t) for a, b in zip((40, 60, 120), (240, 140, 20)))
        d.polygon(T(p.exterior.coords), fill=colour, outline=(255, 255, 255))
    if len(kwh):
        d.rectangle([6, 6, 22, 18], fill=(40, 60, 120))
        d.text((28, 6), f"most shade ({lo:.0f} kWh/yr)", fill=(30, 30, 30))
        d.rectangle([6, 24, 22, 36], fill=(240, 140, 20))
        d.text((28, 24), f"least shade ({hi:.0f} kWh/yr)", fill=(30, 30, 30))
        d.rectangle([6, 42, 22, 54], fill=(255, 240, 150))
        d.text((28, 42), "usable roof (step 2)", fill=(30, 30, 30))
    if dropped:
        d.rectangle([6, 60, 22, 72], fill=(200, 200, 200))
        d.text((28, 60), f"left out: too much shade ({len(dropped)})", fill=(30, 30, 30))
    img.save(path, format="PNG")


def write_hourly(path, times, hourly):
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["time_utc", "kwh"])
        wr.writerows((str(t), round(float(v), 4)) for t, v in zip(times, hourly))


def options_png(fp, usable, items, path):
    """The three layouts of one panel model side by side, with their totals underneath."""
    pics = []
    every = np.concatenate([k for _, _, k, _ in items]) if items else np.zeros(0)
    scale = (every.min(), every.max()) if len(every) else None   # same colours in all three pictures
    for name, layout, kwh, text in items:
        buf = io.BytesIO()
        panels_png(fp, usable, layout, kwh, buf, scale=scale)
        pics.append((Image.open(buf).convert("RGB"), name, text))
    w = sum(p.width for p, _, _ in pics) + 20 * (len(pics) - 1)
    h = max(p.height for p, _, _ in pics) + 50
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    x = 0
    for p, name, text in pics:
        img.paste(p, (x, 0))
        d.text((x + 6, p.height + 8), name, fill=(20, 20, 20))
        d.text((x + 6, p.height + 26), text, fill=(70, 70, 70))
        x += p.width + 20
    img.save(path)


def shade_yield(laz_dir, address=None, lat=None, lon=None, usable_path=None,
                weather_path=DEFAULT_PATH, out="roof", max_shade_loss=MAX_SHADE_LOSS, max_panels=None,
                panel_wp=420, layout_option="max", compare_wp=None, orient="building", panel_size=None, portrait=False):
    """Steps 3 + 4. panel_wp and layout_option pick the layout the main outputs use;
    compare_wp lists the panel wattages to work the three options out for (default: panel_wp only).
    panel_size = (length_m, width_m) replaces the catalogue size of the panel_wp module for this run
    (for example the size of the panel really installed); portrait=True puts the long side up the slope."""
    Path(out).parent.mkdir(parents=True, exist_ok=True)   # data\\pv does not exist on a fresh clone
    if layout_option not in {o["id"] for o in OPTIONS}:
        raise SystemExit(f"unknown layout {layout_option}; choose from {[o['id'] for o in OPTIONS]}")
    modules = dict(MODULES)
    if panel_size or portrait:
        base = modules.get(int(panel_wp)) or Module(int(panel_wp), 2.28, 1.13, "")
        long_m, short_m = panel_size if panel_size else (base.long_m, base.short_m)
        if portrait:
            long_m, short_m = short_m, long_m   # long side up the slope
        modules[int(panel_wp)] = Module(int(panel_wp), long_m, short_m,
                                        f"{int(panel_wp)} W, {max(long_m, short_m):.2f} x {min(long_m, short_m):.2f} m"
                                        f"{', portrait' if portrait else ''} (custom size)")
    elif int(panel_wp) not in modules:
        get_module(panel_wp)   # stops with a clear message
    module = modules[int(panel_wp)]
    wps = sorted({module.wp, *[modules[int(w)].wp for w in (compare_wp or []) if int(w) in modules]})
    record, fp = find_building(address, lat, lon)
    lroof = read_roof_from_tiles(fp, laz_dir, refcat=record.refcat)
    if lroof is None:
        raise SystemExit("No LiDAR tile in --laz-dir covers this building. Download the tile first.")
    if not Path(weather_path).exists():
        raise SystemExit(f"No weather file at {weather_path}. Run: python -m step03_simulate_generation.weather")
    weather = load_tmy(weather_path)
    usable = load_usable(usable_path) if usable_path else lroof.grid.cells_to_polygon(lroof.usable)
    surface = surface_model(fp, laz_dir)

    usable_fc = usable_geojson(usable)
    if usable_path:
        usable_file = str(usable_path)
    else:
        usable_file = f"{out}_usable.geojson"
        Path(usable_file).write_text(json.dumps(usable_fc), encoding="utf-8")

    variants, main, orient_table = [], None, None
    for wp in wps:
        mod = modules[wp]
        full, kwh, loss, _, dropped, per_panel = analyse(
            lroof, fp, laz_dir, weather, record.lat, record.lon, usable, max_shade_loss, max_panels,
            module=mod, surface=surface if surface[0] is not None else None, orient=orient)
        if full.orientation_table and wp == module.wp:
            orient_table = full.orientation_table
        pics = []
        fits = full.count + len(dropped)
        for o, keep, n_blocks, hourly, weak in variants_for(full, kwh, per_panel, weather):
            lay = full.subset(keep)
            summary = summarise(lay, kwh[keep], loss[keep], hourly, weather)
            hourly_file = f"{out}_hourly_{wp}_{o['id']}.csv"
            write_hourly(hourly_file, weather.times, hourly)
            variants.append({
                "panel_wp": wp, "panel": mod.label, "option": o["id"], "name": o["name"], "rule": o["rule"],
                "blocks": n_blocks, **summary, "hourly_file": hourly_file,
                "funnel": {"fit": fits, "shaded_out": len(dropped), "after_shade": full.count,
                           "weak": int((weak & ~keep).sum()), "loose": int((~weak & ~keep).sum()),
                           "kept": int(keep.sum())},
                "left_out": left_out(full, keep, weak),
                "panel_list": [{"x": round(p.centroid.x, 2), "y": round(p.centroid.y, 2),
                                "kwh_year": round(float(k), 1), "corners": corners(p)}
                               for p, k in zip(lay.panels, kwh[keep])]})
            pics.append((f"{o['name']} ({wp} W)", lay, kwh[keep],
                         f"{lay.count} panels, {lay.kwp:.1f} kWp, {summary['yearly_kwh']:,} kWh/yr"))
            if wp == module.wp and o["id"] == layout_option:
                main = (lay, kwh[keep], loss[keep], hourly, dropped)
        if wp == module.wp:
            options_png(fp, usable, pics, f"{out}_options.png")

    layout, kwh, loss, hourly, dropped = main
    result = {
        "building": {"refcat": record.refcat, "address": record.catastro_address, "query": record.query},
        "yield": {**summarise(layout, kwh, loss, hourly, weather), "panels_left_out": len(dropped),
                  "max_shade_loss": max_shade_loss, "panel_wp": module.wp, "layout": layout_option},
        "usable_area_m2": round(usable.area, 1) if usable is not None else 0.0,
        "usable_file": usable_file,
        "roof": roof_summary(lroof, usable, usable_path),   # step 2 numbers
        "lidar": lroof.summary,
        "panels": [{"x": round(p.centroid.x, 2), "y": round(p.centroid.y, 2),
                    "kwh_year": round(float(k), 1), "shade_loss": round(float(s), 3)}
                   for p, k, s in zip(layout.panels, kwh, loss)],
        "variants": variants,
        "orientation": {"mode": orient, "azimuth_deg": round(layout.azimuth_deg, 1), "tried": orient_table},
    }
    Path(f"{out}_yield.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    write_hourly(f"{out}_hourly.csv", weather.times, hourly)
    fc = {"type": "FeatureCollection",
          "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::25831"}},
          "features": [{"type": "Feature", "geometry": mapping(p),
                        "properties": {"kwh_year": round(float(k), 1), "shade_loss": round(float(s), 3)}}
                       for p, k, s in zip(layout.panels, kwh, loss)]}
    Path(f"{out}_panels.geojson").write_text(json.dumps(fc), encoding="utf-8")
    panels_png(fp, usable, layout, kwh, f"{out}_panels.png", dropped)
    return result


def main():
    ap = argparse.ArgumentParser(description="Pipeline steps 3 and 4: panel layout, shade and yield")
    ap.add_argument("address", nargs="?")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--laz-dir", required=True, help="folder with ICGC LAZ tiles")
    ap.add_argument("--usable", help="step 2 usable area (<name>_usable.geojson); leave out to read the roof with LiDAR")
    ap.add_argument("--weather", default=str(DEFAULT_PATH), help="PVGIS typical year (python -m step03_simulate_generation.weather)")
    ap.add_argument("--max-shade", type=float, default=MAX_SHADE_LOSS,
                    help="leave out panels losing more than this share of their sun (default 0.4; 1 keeps all)")
    ap.add_argument("--max-panels", type=int,
                    help="keep only this many panels, best first (default: every panel that fits)")
    ap.add_argument("--panel-wp", type=int, default=420,
                    help="panel watts for the main outputs: 420 (default) or 540 W, or any number with --panel-size")
    ap.add_argument("--panel-size", help="panel length x width in metres, e.g. 2.38x1.13 (replaces the catalogue size "
                                         "of --panel-wp for this run; use the size of the panel really installed)")
    ap.add_argument("--portrait", action="store_true",
                    help="long side of the panel up the slope instead of along the row")
    ap.add_argument("--layout", default="max", choices=[o["id"] for o in OPTIONS],
                    help="layout for the main outputs: max (fill the roof, default), neat or best")
    ap.add_argument("--compare-wp", default="420,540",
                    help="panel wattages to work out all three layouts for (default 420,540)")
    ap.add_argument("--orient", default="building", choices=["building", "south", "search"],
                    help="panel row direction: building = along the building edge nearest south (default), "
                         "south = due south, search = try every 5 degrees around the building axis and keep "
                         "the best panels x sun")
    ap.add_argument("--out", default="roof", help="output name, without extension")
    args = ap.parse_args()
    if not args.address and (args.lat is None or args.lon is None):
        ap.error("give an address, or both --lat and --lon")
    compare = [int(w) for w in args.compare_wp.split(",") if w.strip()]
    size = None
    if args.panel_size:
        try:
            size = tuple(float(x) for x in args.panel_size.lower().replace(",", ".").split("x"))
            assert len(size) == 2 and min(size) > 0.3
        except (ValueError, AssertionError):
            ap.error("--panel-size must look like 2.28x1.13 (metres)")
        compare = [w for w in compare if w == args.panel_wp] or [args.panel_wp]
    result = shade_yield(args.laz_dir, args.address, args.lat, args.lon, args.usable, args.weather, args.out,
                         args.max_shade, args.max_panels, args.panel_wp, args.layout, compare, args.orient, size, args.portrait)
    print(json.dumps({k: result.get(k) for k in ("building", "yield", "usable_area_m2")}, indent=2))
    print("\nLayout options (choose with --panel-wp and --layout):")
    for v in result["variants"]:
        print(f"  {v['panel_wp']} W  {v['option']:<5} {v['name']:<14} {v['panels']:>4} panels "
              f"{v['kwp']:>7.2f} kWp {v['yearly_kwh']:>8,} kWh/yr  {v['kwh_per_kwp'] or 0:>5} kWh/kWp")
    if result["orientation"]["tried"]:
        print("\nOrientations tried (best first): azimuth, offset from building axis, panels, score = panels x sun factor")
        for r in result["orientation"]["tried"][:8]:
            print(f"  {r['azimuth_deg']:>6}  {r['offset_from_building_deg']:>+4}  {r['panels']:>4}  {r['score']:>7}")
    print(f"Pictures: {args.out}_options.png")


if __name__ == "__main__":
    main()
