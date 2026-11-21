"""Rewrite only the roof section (steps 02-03) of website/data/site_data.json.

Use it when steps 02-03 change but the later steps (04-08) have not been rerun yet, for
example the CEP9 run on both roofs. Everything else in site_data.json stays as it is, and
the page says which roof run the sections below still use.

    python -m step09_publish_report.update_roof --yield examples\\cep9_both\\cep9_yield.json ^
        --actual examples\\cep9_actual.json --below-note "..."
"""
import argparse
import json
from pathlib import Path

from .export_site_data import actual_variant, layout_variants


def _rings(geojson_path, to_utm=False, only_role=None, tol=0.2):
    """Outer rings ([[x, y], ...] in EPSG:25831, rounded to 0.1 m) of the polygons in a GeoJSON file."""
    import shapely
    from pyproj import Transformer
    from shapely.geometry import shape
    fc = json.loads(Path(geojson_path).read_text(encoding="utf-8"))
    tr = Transformer.from_crs("EPSG:4326", "EPSG:25831", always_xy=True).transform if to_utm else None
    out = []
    for f in fc["features"]:
        props = f.get("properties") or {}
        if only_role and props.get("role") != only_role:
            continue
        g = shape(f["geometry"])
        if tr:
            g = shapely.transform(g, lambda c: __import__("numpy").column_stack(tr(c[:, 0], c[:, 1])))
        for part in getattr(g.simplify(tol), "geoms", [g.simplify(tol)]):
            if part.area >= 1:
                out.append({"name": props.get("name", ""), "c": [[round(x, 1), round(y, 1)] for x, y in part.exterior.coords]})
    return out


def update_roof(yield_json, actual_json=None, below_note="", out="../website/data/site_data.json", chosen="actual", label=None,
                footprints=None, usable=(), reserved=None):
    ry = json.loads(Path(yield_json).read_text(encoding="utf-8"))
    data = json.loads(Path(out).read_text(encoding="utf-8"))
    variants = layout_variants(ry)
    if actual_json:
        variants.insert(0, actual_variant(json.loads(Path(actual_json).read_text(encoding="utf-8")), variants))
    yl = ry["yield"]
    data["roof"].update({
        "address": label or ry["building"]["query"], "refcat": ry["building"]["refcat"],
        "usable_m2": ry.get("usable_area_m2"), "roofs": ry.get("roofs"),
        "monthly_kwh": yl["monthly_kwh"], "tilt_deg": yl["tilt_deg"], "azimuth_deg": yl["azimuth_deg"],
        "mean_shade_loss": yl["mean_shade_loss"], "panels_left_out": yl["panels_left_out"],
        "panels": [{"x": p["x"], "y": p["y"], "kwh": p["kwh_year"]} for p in ry["panels"]],
        "variants": variants,
        "separate": bool(below_note), "below_note": below_note,
        "chosen": {"panel_wp": yl.get("panel_wp", 540), "option": chosen},
        # drawn under the panels so the layouts sit on their buildings
        "outlines": _rings(footprints, to_utm=True, only_role="host") if footprints else [],
        "usable_areas": [r for u in usable for r in _rings(u, tol=0.3)],
        "reserved_areas": _rings(reserved) if reserved else [],
    })
    Path(out).write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"roof section of {out}: " + "; ".join(f"{v['name']} {v['panel_wp']} W: {v['panels']} panels" for v in variants))


def main():
    ap = argparse.ArgumentParser(description="Rewrite only the roof section of the website data")
    ap.add_argument("--yield", dest="yield_json", required=True, help="step 03 yield file (one roof, or combine_roofs output)")
    ap.add_argument("--actual", help="JSON of the real system (e.g. examples\\cep9_actual.json); adds the Actual tab")
    ap.add_argument("--below-note", default="", help="sentence saying which roof run the sections below still use")
    ap.add_argument("--label", help="what the roof section calls the roof(s), e.g. 'CEP9, Escola Pere IV + Institut Quatre Cantons'")
    ap.add_argument("--footprints", help="step 01 case map (cases/<case>_map.geojson, WGS84): host roof outlines to draw")
    ap.add_argument("--usable", action="append", default=[], help="step 02 <out>_usable.geojson to draw as the usable roof; repeat per roof")
    ap.add_argument("--reserved", help="reserved-areas GeoJSON (EPSG:25831) given to step 02, drawn dashed")
    ap.add_argument("--out", default="../website/data/site_data.json")
    a = ap.parse_args()
    update_roof(a.yield_json, a.actual, a.below_note, a.out, label=a.label,
                footprints=a.footprints, usable=a.usable, reserved=a.reserved)


if __name__ == "__main__":
    main()
