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


def update_roof(yield_json, actual_json=None, below_note="", out="../website/data/site_data.json", chosen="actual", label=None):
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
    })
    Path(out).write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"roof section of {out}: " + "; ".join(f"{v['name']} {v['panel_wp']} W: {v['panels']} panels" for v in variants))


def main():
    ap = argparse.ArgumentParser(description="Rewrite only the roof section of the website data")
    ap.add_argument("--yield", dest="yield_json", required=True, help="step 03 yield file (one roof, or combine_roofs output)")
    ap.add_argument("--actual", help="JSON of the real system (e.g. examples\\cep9_actual.json); adds the Actual tab")
    ap.add_argument("--below-note", default="", help="sentence saying which roof run the sections below still use")
    ap.add_argument("--label", help="what the roof section calls the roof(s), e.g. 'CEP9, Escola Pere IV + Institut Quatre Cantons'")
    ap.add_argument("--out", default="../website/data/site_data.json")
    a = ap.parse_args()
    update_roof(a.yield_json, a.actual, a.below_note, a.out, label=a.label)


if __name__ == "__main__":
    main()
