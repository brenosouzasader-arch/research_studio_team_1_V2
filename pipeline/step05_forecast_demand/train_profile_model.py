"""Step 05: train a demand model from real Spanish smart-meter data, by building type.

WHY: today (baseline_profiles.py) every guest's use is a rule of thumb. This script learns
two things from real meters instead:

  1. DAILY AVERAGES: how many kWh a day a supply point of a given type uses, by month and
     weekday/weekend, per kW of contracted power (a stand-in for size).
  2. TIME-OF-DAY AVERAGES: the share of the day's use that falls in each hour, by type,
     season and weekday/weekend.
  3. A gradient-boosting MODEL for (1) that also looks at contracted power, tested on
     customers it never saw and compared with the plain averages (the baseline).

DATA: the GoiEner smart-meter dataset (Zenodo 10.5281/zenodo.7362094, CC BY 4.0 per its paper):
25,559 Spanish supply points, hourly kWh, with a CNAE activity code and contracted power in
metadata.csv [Scientific Data 2024, doi 10.1038/s41597-023-02846-0]. Mostly Basque Country
and Navarre households, with offices, shops, public buildings and others in smaller numbers.
Barcelona is NOT in it, so the result is a Spanish prediction, not a measured Barcelona one.

HOW TO GET THE DATA (on your laptop, about 0.5-2 GB):
  https://zenodo.org/records/7362094/files/metadata.csv?download=1
  https://zenodo.org/records/7362094/files/imp-in.tzst?download=1   (555.9 MB, gaps filled)
  unpack imp-in.tzst (zstd tar) so there is one csv per supply point in --series-dir.
  The column names below were NOT checked against the files (we could not download them
  from the cloud): the script prints the columns it finds and stops with a clear message
  if the id, cnae, power or timestamp columns are not where it expects. Fix COLUMN_ALIASES.

RUN:
  python -m step05_forecast_demand.train_profile_model --metadata data\\goiener\\metadata.csv ^
      --series-dir data\\goiener\\imp-in --out data\\models\\demand_profile --max-series 3000

OUTPUT in --out: daily_averages.csv, hourly_shape.csv, model.joblib, report.json (error on
held-out customers vs the baseline, and how many series of each type were used).
"""
import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

TZ = "Europe/Madrid"

# metadata.csv / series column names we try, in order (ASSUMPTION: not verified on the real files)
COLUMN_ALIASES = {
    "id": ["user", "id", "cups", "customer", "supply_point"],
    "cnae": ["cnae", "cnae_code"],
    "power": ["p1", "contracted_power", "power_kw"],
    "time": ["timestamp", "datetime", "date", "time"],
    "kwh": ["kWh", "kwh", "value", "consumption"],
}

# CNAE 2009 two-digit division -> building type. Our grouping (ASSUMPTION: chosen to match the
# building types we meet in Poblenou); CNAE divisions themselves are the INE classification.
GROUPS = [
    ("household", {97, 98}),
    ("public_admin", {84}),
    ("education", {85}),
    ("health_social", set(range(86, 89))),
    ("hospitality", {55, 56}),
    ("retail", set(range(45, 48))),
    ("transport_storage", set(range(49, 54))),
    ("office", set(range(58, 83))),
    ("industry", set(range(5, 34))),
]
BASE_TYPE = "other"


def cnae_group(code):
    """'8510', '85.10', 8510 or '85' -> 'education'. Unknown or missing -> 'other'."""
    digits = re.sub(r"\D", "", str(code))
    if len(digits) < 2:
        return BASE_TYPE
    division = int(digits[:2])
    for name, divisions in GROUPS:
        if division in divisions:
            return name
    return BASE_TYPE


def pick(columns, key):
    lower = {c.lower(): c for c in columns}
    for alias in COLUMN_ALIASES[key]:
        if alias.lower() in lower:
            return lower[alias.lower()]
    raise SystemExit(f"No '{key}' column. Columns found: {list(columns)}. Edit COLUMN_ALIASES in {__file__}")


def season(month):
    return {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
            6: "summer", 7: "summer", 8: "summer"}.get(month, "autumn")


def read_series(path):
    """One supply point's csv -> hourly kWh Series in Madrid local time."""
    df = pd.read_csv(path)
    t, k = pick(df.columns, "time"), pick(df.columns, "kwh")
    idx = pd.to_datetime(df[t], utc=True).dt.tz_convert(TZ)
    return pd.Series(pd.to_numeric(df[k], errors="coerce").values, index=idx).dropna()


def daily_and_shape(hourly):
    """Hourly Series -> (daily table, hourly table). Only complete 24-hour days are kept."""
    h = hourly[~hourly.index.duplicated()]
    counts = h.groupby(h.index.date).transform("count")
    h = h[counts >= 24]
    if h.empty:
        return None, None
    day = h.groupby(h.index.date).sum()
    daily = pd.DataFrame({"kwh_day": day.values}, index=pd.to_datetime(list(day.index)))
    daily["month"] = daily.index.month
    daily["weekend"] = (daily.index.day_of_week >= 5).astype(int)
    total = h.groupby(h.index.date).transform("sum")
    keep = total > 0
    share = (h[keep] / total[keep])
    hours = pd.DataFrame({"share": share.values, "hour": share.index.hour,
                          "month": share.index.month, "weekend": (share.index.day_of_week >= 5).astype(int)})
    return daily, hours


def collect(metadata_csv, series_dir, max_series=None, seed=0):
    meta = pd.read_csv(metadata_csv)
    c_id, c_cnae, c_pow = pick(meta.columns, "id"), pick(meta.columns, "cnae"), pick(meta.columns, "power")
    meta = meta.assign(btype=meta[c_cnae].map(cnae_group))
    # any file under series_dir (sub-folders included); the id is the file name up to the first dot
    files = {p.name.split(".")[0]: p for p in Path(series_dir).rglob("*") if p.is_file()}
    ids = meta[c_id].astype(str)
    print(f"metadata rows: {len(meta)}; series files found: {len(files)}; matching ids: {int(ids.isin(files).sum())}")
    if not ids.isin(files).any():
        raise SystemExit(f"No series file matches a metadata id.\n  first ids in metadata ({c_id}): {list(ids[:3])}"
                         f"\n  first files in {series_dir}: {[p.name for p in list(Path(series_dir).rglob('*'))[:5]]}")
    meta = meta[ids.isin(files)]
    if max_series and len(meta) > max_series:   # keep every non-household type, sample households
        rest = meta[meta.btype != "household"]
        hh = meta[meta.btype == "household"].sample(max(0, max_series - len(rest)), random_state=seed)
        meta = pd.concat([rest, hh])
    dailies, shapes = [], []
    for n, (_, row) in enumerate(meta.iterrows(), 1):
        if n % 200 == 0:
            print(f"  read {n} of {len(meta)} series", flush=True)
        sid = str(row[c_id])
        try:
            d, s = daily_and_shape(read_series(files[sid]))
        except SystemExit:
            raise
        except Exception as e:   # one bad file must not stop the run, but say why
            print(f"skipped {files[sid].name}: {e!r}")
            continue
        if d is None:
            continue
        kw = float(row[c_pow]) if pd.notna(row[c_pow]) and row[c_pow] > 0 else np.nan
        d = d.assign(sid=sid, btype=row["btype"], kw=kw)
        s = s.assign(sid=sid, btype=row["btype"])
        dailies.append(d)
        shapes.append(s)
    if not dailies:
        raise SystemExit("No series could be read.")
    return pd.concat(dailies), pd.concat(shapes)


def daily_table(daily):
    """Average kWh per day, and per contracted kW, for every type x month x weekday/weekend."""
    d = daily.assign(kwh_per_kw=daily.kwh_day / daily.kw)
    g = d.groupby(["btype", "month", "weekend"])
    out = g.agg(kwh_day_mean=("kwh_day", "mean"), kwh_day_median=("kwh_day", "median"),
                kwh_per_kw_mean=("kwh_per_kw", "mean"), supply_points=("sid", "nunique"),
                days=("kwh_day", "size")).reset_index()
    return out.round(3)


def shape_table(shapes):
    """Share of the day's kWh in each hour, per type x season x weekday/weekend (sums to 1 per group)."""
    s = shapes.assign(season=shapes.month.map(season))
    out = s.groupby(["btype", "season", "weekend", "hour"]).share.mean().reset_index()
    out["share"] = out.share / out.groupby(["btype", "season", "weekend"]).share.transform("sum")
    return out.round(5)


FEATURES = ["btype_code", "log_kw", "month", "weekend"]


def _x(df, types):
    return pd.DataFrame({"btype_code": df.btype.map({t: i for i, t in enumerate(types)}),
                         "log_kw": np.log(df.kw), "month": df.month, "weekend": df.weekend})


def train(daily, seed=0):
    """Gradient boosting on log kWh/day, tested on customers held out entirely.

    Baseline = the plain average per type x month x weekday/weekend (what the tables give).
    Returns (model, types, report)."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    d = daily.dropna(subset=["kw"])
    d = d[d.kwh_day > 0]
    types = sorted(d.btype.unique())
    ids = np.array(sorted(d.sid.unique()))
    rng = np.random.default_rng(seed)
    test_ids = set(rng.choice(ids, size=max(1, len(ids) // 5), replace=False))
    test = d[d.sid.isin(test_ids)]
    fit = d[~d.sid.isin(test_ids)]
    model = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.08, random_state=seed)
    model.fit(_x(fit, types), np.log(fit.kwh_day))
    pred = np.exp(model.predict(_x(test, types)))
    base = fit.groupby(["btype", "month", "weekend"]).kwh_day.mean().rename("base").reset_index()
    base_pred = test.merge(base, on=["btype", "month", "weekend"], how="left").base.fillna(fit.kwh_day.mean()).values
    # error in kWh per day, and as a share of the held-out average day
    mae = float(np.mean(np.abs(pred - test.kwh_day.values)))
    mae_base = float(np.mean(np.abs(base_pred - test.kwh_day.values)))
    per_type = {}
    for t in types:
        m = (test.btype == t).values
        if m.sum():
            per_type[t] = {"held_out_days": int(m.sum()),
                           "model_mae_kwh_day": round(float(np.mean(np.abs(pred[m] - test.kwh_day.values[m]))), 2),
                           "baseline_mae_kwh_day": round(float(np.mean(np.abs(base_pred[m] - test.kwh_day.values[m]))), 2)}
    report = {"supply_points": int(len(ids)), "held_out_supply_points": len(test_ids),
              "model_mae_kwh_day": round(mae, 2), "baseline_mae_kwh_day": round(mae_base, 2),
              "model_beats_baseline": mae < mae_base, "per_type": per_type,
              "supply_points_per_type": d.groupby("btype").sid.nunique().to_dict()}
    return model, types, report


def run(metadata, series_dir, out, max_series=None):
    import joblib
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    daily, shapes = collect(metadata, series_dir, max_series)
    daily_table(daily).to_csv(out / "daily_averages.csv", index=False)
    shape_table(shapes).to_csv(out / "hourly_shape.csv", index=False)
    model, types, report = train(daily)
    joblib.dump({"model": model, "types": types, "features": FEATURES}, out / "model.joblib")
    (out / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--metadata", required=True)
    ap.add_argument("--series-dir", required=True)
    ap.add_argument("--out", default="data/models/demand_profile")
    ap.add_argument("--max-series", type=int, default=None, help="cap the number of supply points (households are sampled)")
    a = ap.parse_args()
    run(a.metadata, a.series_dir, a.out, a.max_series)
