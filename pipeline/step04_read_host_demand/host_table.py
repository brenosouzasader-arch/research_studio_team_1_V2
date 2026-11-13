"""Step 04: read the host's demand and line it up with its solar output, hour by hour.

This is the roadmap's Week 1 gate: host PV + host load in one 8,760-hour table.

    surplus[h] = max(0, G[h] - D[host,h])

Host demand comes from one of two places (the source is written in every row):
- metered (best): a CSV with a time column and a kWh column, any interval (15 min from
  UPC SIRENA, hourly from Datadis), times in UTC. It is added up per hour and matched to
  the solar year by month, day and hour.
      python -m step04_read_host_demand.host_table --solar data\\pv\\nexus2_hourly.csv ^
          --metered data\\meters\\nexus2.csv --building-id nexus2 --out data\\host\\nexus2
- proxy (no meter): step 05's baseline profile from a floor area and a use type.
      python -m step04_read_host_demand.host_table --solar examples\\bruc59_hourly.csv ^
          --host-kind office --host-floor-m2 1500 --building-id demo_office --out data\\host\\demo

Outputs in the --out folder (file names and columns follow the roadmap's specification):
- pv_hourly.csv       timestamp_utc, generation_kwh, irradiance_source, shade_loss, model_version
- demand_hourly.csv   building_id, timestamp_utc, consumed_kwh, source_type, quality_flag
- host_table.csv      timestamp_utc, generation_kwh, host_demand_kwh, self_consumed_kwh, surplus_kwh
- host_summary.json   totals, self-consumption ratio, surplus by month and weekday vs weekend
- surplus_map.png     365 days (rows) x 24 hours (columns), darker = more surplus

If the surplus is small, that is a result: sharing does not pay for this host.
The surplus-first rule comes from V1's step 5b (sharing.py); the rest is new in V2.
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from step05_forecast_demand import baseline_profiles as dm

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def read_hourly(path):
    """Step 4's <name>_hourly.csv -> (times as datetime64[m] UTC, kWh per hour)."""
    times, kwh = [], []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            times.append(r["time_utc"])
            kwh.append(float(r["kwh"]))
    return np.array(times, dtype="datetime64[m]"), np.array(kwh)


def _key(t):
    """(month, day, hour) of a datetime64, so a meter year lines up with the typical solar year."""
    t = np.asarray(t, dtype="datetime64[m]")
    month = t.astype("datetime64[M]").astype(int) % 12 + 1
    day = (t.astype("datetime64[D]") - t.astype("datetime64[M]")).astype(int) + 1
    hour = (t - t.astype("datetime64[D]")).astype("timedelta64[h]").astype(int)
    return month * 10000 + day * 100 + hour


def align_to_year(t, ref):
    """Move meter times into the solar file's calendar year, keeping weekdays.
    Each meter year is moved by whole years and then by up to 3 days, so a Monday stays a
    Monday (an office's weekend must stay a weekend). Public holidays may move by a few days."""
    t = np.asarray(t, dtype="datetime64[m]")
    years = t.astype("datetime64[Y]").astype(int) + 1970
    ref_year = int(np.datetime64(ref, "Y").astype(int)) + 1970
    out = t.copy()
    for y in np.unique(years):
        jan_meter = np.datetime64(f"{y}-01-01")
        jan_ref = np.datetime64(f"{ref_year}-01-01")
        k = (int(jan_ref.astype(int)) - int(jan_meter.astype(int))) % 7      # weekday difference
        days = int((jan_ref - jan_meter).astype(int)) - (k if k <= 3 else k - 7)
        m = years == y
        out[m] = t[m] + np.timedelta64(days, "D")
    return out, years


def read_metered(path, solar_times, time_col=None, kwh_col=None):
    """A meter export (any interval, times in UTC) -> kWh for each hour of the solar year.
    Hours the meter does not cover are filled with the mean of the same weekday hour."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"{path} is empty")
    cols = list(rows[0])
    time_col = time_col or next((c for c in cols if "time" in c.lower() or "date" in c.lower()), cols[0])
    kwh_col = kwh_col or next((c for c in cols if "kwh" in c.lower()), cols[1])
    t = np.array([r[time_col].replace(" ", "T")[:16] for r in rows], dtype="datetime64[m]")
    v = np.array([float(r[kwh_col] or 0) for r in rows])
    shifted, year_of = align_to_year(t, np.asarray(solar_times, dtype="datetime64[m]")[0])
    sums = {}
    for y, k, x in zip(year_of, _key(shifted), v):
        sums[(y, k)] = sums.get((y, k), 0.0) + x       # kWh per hour, per meter year
    per_hour = {}
    for (_, k), x in sums.items():
        per_hour.setdefault(k, []).append(x)
    per_hour = {k: float(np.mean(x)) for k, x in per_hour.items()}   # several years -> average year
    keys = _key(solar_times)
    use = np.array([per_hour.get(k, np.nan) for k in keys])
    if np.isnan(use).all():
        raise SystemExit("The meter file covers none of the hours of the solar year")
    if np.isnan(use).any():
        hour, weekday, _ = dm.local_hours(solar_times)
        slot = weekday * 24 + hour
        for s in np.unique(slot[np.isnan(use)]):
            same = (slot == s) & ~np.isnan(use)
            use[(slot == s) & np.isnan(use)] = use[same].mean() if same.any() else np.nanmean(use)
    return use


def predicted_use(solar_times, kind, floor_m2):
    """Host use from step 5's demand model: floor area x kWh per m2, spread with the kind's day shape."""
    shapes = dm.profile_shapes(solar_times)
    per_m2 = dm.KIND_PER_M2.get(kind, dm.COMMERCIAL_KWH_PER_M2)
    return floor_m2 * per_m2 * shapes.get(kind, shapes["shop"])


def surplus_map(solar, host_use):
    self_used = np.minimum(solar, host_use)
    return self_used, solar - self_used


def summarise(times, solar, host_use, self_used, surplus):
    hour, weekday, month = dm.local_hours(times)
    weekend = weekday >= 5
    total = solar.sum()
    by_month = {MONTHS[m - 1]: round(float(surplus[month == m].sum())) for m in range(1, 13)}
    return {
        "generation_kwh": round(float(total)),
        "host_demand_kwh": round(float(host_use.sum())),
        "self_consumed_kwh": round(float(self_used.sum())),
        "self_consumption_ratio": round(float(self_used.sum() / solar.sum()), 3) if solar.sum() else 0.0,
        "surplus_kwh": round(float(surplus.sum())),
        "surplus_share": round(float(surplus.sum() / total), 3) if total else 0.0,
        "hours_with_surplus": int((surplus > 0.01).sum()),
        "surplus_weekday_kwh": round(float(surplus[~weekend].sum())),
        "surplus_weekend_kwh": round(float(surplus[weekend].sum())),
        "surplus_by_month_kwh": by_month,
    }


def draw_map(times, surplus, path, cell=3):
    """365 x 24 picture: one row per day, one column per local hour, white = none, dark orange = most."""
    hour, _, _ = dm.local_hours(times)
    day = (np.asarray(times, dtype="datetime64[D]") - np.asarray(times, dtype="datetime64[D]").min()).astype(int)
    days = int(day.max()) + 1
    grid = np.zeros((days, 24))
    np.add.at(grid, (day, hour), surplus)
    top = grid.max() or 1.0
    x = (grid / top)[..., None]
    rgb = (255 * (1 - x) + np.array([200, 80, 0]) * x).astype(np.uint8)
    img = Image.fromarray(rgb).resize((24 * cell * 4, days * cell), Image.NEAREST)
    canvas = Image.new("RGB", (img.width + 50, img.height + 30), "white")
    canvas.paste(img, (40, 20))
    d = ImageDraw.Draw(canvas)
    d.text((40, 4), "Surplus by day (rows, Jan at top) and hour (columns, 0-23 h)", fill=(30, 30, 30))
    for h in (0, 6, 12, 18):
        d.text((40 + h * cell * 4, img.height + 20), str(h), fill=(30, 30, 30))
    canvas.save(path)


MODEL_VERSION = "v2-steps02-03"


def run(solar_csv, out_dir, metered=None, host_kind="office", host_floor_m2=None, building_id="host",
        irradiance_source="PVGIS TMY"):
    times, solar = read_hourly(solar_csv)
    if metered:
        host_use, source, flag = read_metered(metered, times), "metered", "ok"
    elif host_floor_m2:
        host_use, source, flag = predicted_use(times, host_kind, host_floor_m2), f"proxy_{host_kind}", "assumed"
    else:
        raise SystemExit("Give --metered (a meter CSV) or --host-floor-m2 (to use a proxy profile)")
    self_used, surplus = surplus_map(solar, host_use)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamps = [str(t) + ":00Z" for t in times]
    _write(out_dir / "pv_hourly.csv", ["timestamp_utc", "generation_kwh", "irradiance_source", "shade_loss", "model_version"],
           ([s, round(float(g), 4), irradiance_source, "", MODEL_VERSION] for s, g in zip(stamps, solar)))
    _write(out_dir / "demand_hourly.csv", ["building_id", "timestamp_utc", "consumed_kwh", "source_type", "quality_flag"],
           ([building_id, s, round(float(d), 4), source, flag] for s, d in zip(stamps, host_use)))
    _write(out_dir / "host_table.csv", ["timestamp_utc", "generation_kwh", "host_demand_kwh", "self_consumed_kwh", "surplus_kwh"],
           ([s] + [round(float(v), 4) for v in row] for s, row in zip(stamps, zip(solar, host_use, self_used, surplus))))
    summary = {"building_id": building_id, "solar_file": str(solar_csv), "demand_source": source,
               "metered_file": str(metered) if metered else None,
               **summarise(times, solar, host_use, self_used, surplus)}
    (out_dir / "host_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    draw_map(times, surplus, out_dir / "surplus_map.png")
    return summary


def _write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def read_host_table(out_dir):
    """host_table.csv written by run() -> dict of arrays, for steps 06-08."""
    cols = {"generation_kwh": [], "host_demand_kwh": [], "self_consumed_kwh": [], "surplus_kwh": []}
    times = []
    with open(Path(out_dir) / "host_table.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            times.append(r["timestamp_utc"].rstrip("Z")[:16])
            for c in cols:
                cols[c].append(float(r[c]))
    out = {c: np.array(v) for c, v in cols.items()}
    out["times"] = np.array(times, dtype="datetime64[m]")
    return out


def main():
    ap = argparse.ArgumentParser(description="Step 04: host demand + solar in one 8,760-hour table")
    ap.add_argument("--solar", required=True, help="step 03's <name>_hourly.csv for the host roof")
    ap.add_argument("--metered", help="the host's meter export (CSV with a time column and a kWh column, UTC)")
    ap.add_argument("--host-kind", default="office", choices=["office", "school", "shop"],
                    help="proxy profile when there is no meter")
    ap.add_argument("--host-floor-m2", type=float, help="the host's floor area, for the proxy profile")
    ap.add_argument("--building-id", default="host", help="cadastral id or a short name")
    ap.add_argument("--out", default="data/host", help="output folder")
    args = ap.parse_args()
    s = run(args.solar, args.out, args.metered, args.host_kind, args.host_floor_m2, args.building_id)
    print(json.dumps(s, indent=2))
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
