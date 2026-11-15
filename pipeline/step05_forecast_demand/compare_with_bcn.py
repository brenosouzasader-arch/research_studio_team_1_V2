"""Compare the GoiEner-trained shapes with real Barcelona data (Open Data BCN / Datadis).

The Barcelona file is written by bcn_data.py (data/weather/bcn_usage_profile.json): for homes and
for services (shops, offices and everything else in the tertiary sector) it holds the share of the
day's use in four 6-hour bands, the weekend/weekday ratio and the month-by-month pattern.
The GoiEner tables are in examples/demand_model/ (train_profile_model.py).

    python -m step05_forecast_demand.bcn_data --site poblenou_quatre_cantons
    python -m step05_forecast_demand.compare_with_bcn

Prints, per type: band shares on weekdays, weekend/weekday ratio, and how closely the month
pattern follows Barcelona's (correlation). 'Services' in Barcelona mixes many kinds of business, so it is
put next to each GoiEner business type; it is not expected to match any one of them exactly.
Sources: Open Data BCN dataset consum-electricitat-bcn (CC BY 4.0, Datadis);
GoiEner [Scientific Data 2024].
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

PAIRS = [("home", ["household"]),
         ("shop", ["retail", "office", "public_admin", "education", "hospitality", "health_social"])]


def goiener_summary(model_dir, btype):
    hs = pd.read_csv(Path(model_dir) / "hourly_shape.csv")
    da = pd.read_csv(Path(model_dir) / "daily_averages.csv")
    h = hs[hs.btype == btype]
    bands = {}
    for wk, name in ((0, "weekday"), (1, "weekend")):
        by_hour = h[h.weekend == wk].groupby("hour").share.mean().reindex(range(24)).fillna(0).values
        v = np.array([by_hour[i * 6:(i + 1) * 6].sum() for i in range(4)])
        bands[name] = v / v.sum()
    d = da[da.btype == btype].pivot(index="month", columns="weekend", values="kwh_day_mean").reindex(range(1, 13))
    month = (d[0] * 5 + d[1] * 2) / 7
    return {"bands": bands, "weekend_ratio": float((d[1] / d[0]).mean()), "month": (month / month.mean()).values}


def compare(profile_path, model_dir):
    bcn = json.loads(Path(profile_path).read_text(encoding="utf-8"))
    rows = []
    for kind, types in PAIRS:
        if kind not in bcn:
            continue
        b = bcn[kind]
        rows.append({"type": f"Barcelona {kind}", "night 0-6": b["band_share"]["weekday"][0],
                     "morning 6-12": b["band_share"]["weekday"][1], "afternoon 12-18": b["band_share"]["weekday"][2],
                     "evening 18-24": b["band_share"]["weekday"][3], "weekend/weekday": b["weekend_vs_weekday"],
                     "month correlation": 1.0})
        have = set(pd.read_csv(Path(model_dir) / "daily_averages.csv").btype)
        for t in [t for t in types if t in have]:
            g = goiener_summary(model_dir, t)
            v = g["bands"]["weekday"]
            rows.append({"type": f"  GoiEner {t}", "night 0-6": v[0], "morning 6-12": v[1], "afternoon 12-18": v[2],
                         "evening 18-24": v[3], "weekend/weekday": g["weekend_ratio"],
                         "month correlation": float(np.corrcoef(g["month"], b["month_factor"])[0, 1])})
    return pd.DataFrame(rows).round(2)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bcn-profile", default="data/weather/bcn_usage_profile.json")
    ap.add_argument("--model-dir", default="examples/demand_model")
    a = ap.parse_args()
    if not Path(a.bcn_profile).exists():
        raise SystemExit(f"{a.bcn_profile} not found. Run first: python -m step05_forecast_demand.bcn_data --site poblenou_quatre_cantons")
    print(compare(a.bcn_profile, a.model_dir).to_string(index=False))
