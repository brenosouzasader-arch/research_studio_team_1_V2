"""Step 06b: forecast the hourly price 2 to 7 days ahead, and check it beats a simple rule.

    python -m step06_prices_and_battery.price_model --prices data\\prices\\pvpc_hourly.csv --out data\\prices

WHY: tomorrow's prices are published around 13:00 today (the OMIE day-ahead market closes
at 12:00 CET; see docs/SOURCES.md), so the battery always knows the next 11-35 hours for
sure. A forecast only helps with planning further ahead: should the battery keep some charge
for a dear Monday evening, or is a cheap windy week coming? It also gives the investment step
a price year that is not just the past.

WHAT IT PREDICTS: the PVPC price (EUR/kWh) of one hour, d days before that hour (d = 2..7).

THE MODEL: a gradient-boosted decision tree (scikit-learn HistGradientBoostingRegressor;
the same family as XGBoost and LightGBM). Inputs, all known d days before the hour:
- local clock hour, weekday, month, weekend yes/no
- the price of the same hour d days earlier (the latest one we know)
- the price of the same hour 7 and 14 days earlier
- the mean price of the last known day (the 24 hours ending d days before)
- the "typical year" price of that hour (mean of the training years, same month, day type, hour)
Trained on 2023-2024, tested on 2025 (a year it never saw).

THE BASELINES IT MUST BEAT (the roadmap asks for a simple rule to compare with):
- same_hour_last_week: the price 7 days earlier (for d = 7 this is also the latest known)
- typical_year: the mean of the training years for that month, day type and hour

Output: price_model_report.json with MAE and RMSE (EUR/kWh) of the model and both baselines,
per horizon d. If the model does not beat the baselines, the report says so and the tool
should use the better baseline.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from step06_prices_and_battery.prices import DEFAULT_FILE, MADRID, PVPC, read_prices

HORIZONS = (2, 3, 4, 5, 6, 7)
TRAIN_YEARS = (2023, 2024)
TEST_YEAR = 2025


def hourly_series(prices, series=PVPC):
    """{UTC hour: price} -> (hours as datetime64[h], values), one value per hour, gaps filled from a week before."""
    d = prices[series]
    start, end = min(d), max(d)
    hours = np.arange(start, end + np.timedelta64(1, "h"), dtype="datetime64[h]")
    v = np.array([d.get(h, np.nan) for h in hours])
    for k in np.where(np.isnan(v))[0]:
        v[k] = v[k - 168] if k >= 168 else np.nanmean(v[:168])
    return hours, v


def calendar(hours):
    from datetime import datetime, timezone
    loc = [datetime.fromisoformat(str(h) + ":00").replace(tzinfo=timezone.utc).astimezone(MADRID) for h in hours]
    hour = np.array([t.hour for t in loc])
    wday = np.array([t.weekday() for t in loc])
    month = np.array([t.month for t in loc])
    year = np.array([t.year for t in loc])
    return hour, wday, month, year


def typical_table(v, hour, wday, month, mask):
    """Mean price by (month, weekend?, hour) over the rows in mask."""
    table = np.zeros((13, 2, 24))
    weekend = (wday >= 5).astype(int)
    for m in range(1, 13):
        for w in (0, 1):
            for h in range(24):
                sel = mask & (month == m) & (weekend == w) & (hour == h)
                table[m, w, h] = v[sel].mean() if sel.any() else np.nan
    return table


def features(v, hour, wday, month, typical, d):
    """Feature matrix for horizon d days; rows with too little history are NaN."""
    n = len(v)
    lag = lambda k: np.concatenate([np.full(k, np.nan), v[:-k]])
    day_mean = np.convolve(v, np.ones(24) / 24, mode="full")[:n]          # mean of the 24 h ending at each hour
    last_day_mean = np.concatenate([np.full(24 * d, np.nan), day_mean[:-24 * d]])
    typ = typical[month, (wday >= 5).astype(int), hour]
    X = np.column_stack([hour, wday, month, wday >= 5, lag(24 * d), lag(168), lag(336), last_day_mean, typ])
    return X


def evaluate(y, pred):
    e = pred - y
    return {"mae": round(float(np.mean(np.abs(e))), 4), "rmse": round(float(np.sqrt(np.mean(e ** 2))), 4)}


def train_and_test(prices, horizons=HORIZONS, train_years=TRAIN_YEARS, test_year=TEST_YEAR):
    from sklearn.ensemble import HistGradientBoostingRegressor
    hours, v = hourly_series(prices)
    hour, wday, month, year = calendar(hours)
    train = np.isin(year, train_years)
    test = year == test_year
    typical = typical_table(v, hour, wday, month, train)
    report = {"what": "PVPC EUR/kWh, forecast d days ahead; trained on " + ", ".join(map(str, train_years))
                      + f", tested on {test_year}",
              "test_hours": int(test.sum()), "mean_price_test": round(float(v[test].mean()), 4), "horizons": {}}
    models = {}
    for d in horizons:
        X = features(v, hour, wday, month, typical, d)
        ok = ~np.isnan(X).any(1)
        model = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=0)
        model.fit(X[train & ok], v[train & ok])
        t = test & ok
        res = {"model": evaluate(v[t], model.predict(X[t])),
               "same_hour_last_week": evaluate(v[t], X[t, 5]),
               "typical_year": evaluate(v[t], X[t, 8])}
        best_baseline = min(("same_hour_last_week", "typical_year"), key=lambda k: res[k]["mae"])
        res["model_beats_baselines"] = res["model"]["mae"] < res[best_baseline]["mae"]
        res["error_cut_vs_best_baseline"] = round(1 - res["model"]["mae"] / res[best_baseline]["mae"], 3)
        report["horizons"][f"{d}_days"] = res
        models[d] = model
    return report, models, typical


def main():
    ap = argparse.ArgumentParser(description="Step 06b: PVPC price forecast vs simple rules")
    ap.add_argument("--prices", default=str(DEFAULT_FILE))
    ap.add_argument("--out", default="data/prices")
    args = ap.parse_args()
    report, _, _ = train_and_test(read_prices(args.prices))
    Path(args.out).mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "price_model_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Test year mean price {report['mean_price_test']:.3f} EUR/kWh. Mean error (MAE, EUR/kWh):")
    print("  days ahead   model   same hour last week   typical year")
    for k, r in report["horizons"].items():
        print(f"  {k:>10}   {r['model']['mae']:.4f}   {r['same_hour_last_week']['mae']:.4f}"
              f"                {r['typical_year']['mae']:.4f}   {'model wins' if r['model_beats_baselines'] else 'baseline wins'}")
    print(f"-> {args.out}/price_model_report.json")


if __name__ == "__main__":
    main()
