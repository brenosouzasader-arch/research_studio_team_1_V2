"""Step 06a: read real Spanish electricity prices and line them up with the solar year.

    python -m step06_prices_and_battery.prices --prices data\\prices\\pvpc_hourly.csv --out data\\prices

WHY: in Spain the grid price changes every hour (every 15 minutes on the wholesale market
since 1 Oct 2025). A battery earns money by storing midday solar and using it in the
expensive evening hours, so we need real hourly prices, not one flat price.

THE FILE (made by download_prices.py from REE's free REData API, see docs/SOURCES.md):
    datetime,series,eur_mwh
    2023-01-01T00:00:00.000+01:00,PVPC,41.45
Two series are used:
- "PVPC"                 what a small consumer (under 10 kW) pays for each kWh, per hour.
                         We use it as the value of every kWh the host or a guest does NOT
                         buy from the grid. (Big buildings pay differently: see 3.0TD below.)
- "Precio mercado spot"  the OMIE day-ahead (wholesale) price. We use it as the value of a
                         kWh exported to the grid (ASSUMPTION: export is paid at the
                         wholesale price). Hourly until Sep 2025, then 15-minute; we average
                         the quarters of each hour.
We checked this file against OMIE's own files: 99.7% of hours from Jan 2023 to Sep 2025
match to the cent (the rest are the clock-change days).

LINING UP WITH THE SOLAR YEAR: the solar output (step 03) is a "typical year" whose dates
are 2023. For each solar hour we take the price of the same hour in the chosen price year,
moved by whole weeks so a Monday stays a Monday (offices and schools are closed at weekends,
and weekend prices are lower). "typical" = the average of 2023, 2024 and 2025 after this step.

Outputs in --out:
- prices_hourly_solar_year.csv   timestamp_utc, then pvpc_<year> and spot_<year> in EUR/kWh
- prices_summary.json            per year: mean, cheapest and dearest hour, average daily
                                 shape (24 values, local time), and how often the evening
                                 is dearer than midday (the battery's chance to earn)
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

MADRID = ZoneInfo("Europe/Madrid")
YEARS = (2023, 2024, 2025)
PVPC = "PVPC"
SPOT = "Precio mercado spot"
DEFAULT_FILE = Path("data/prices/pvpc_hourly.csv")


def read_prices(path=DEFAULT_FILE):
    """REE file -> {series: {UTC hour as datetime64[h]: EUR/kWh}}. 15-minute values are averaged per hour."""
    sums = defaultdict(lambda: defaultdict(float))
    counts = defaultdict(lambda: defaultdict(int))
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = datetime.fromisoformat(r["datetime"]).astimezone(timezone.utc).replace(tzinfo=None)
            h = np.datetime64(t.replace(minute=0, second=0, microsecond=0), "h")
            sums[r["series"]][h] += float(r["eur_mwh"]) / 1000.0     # EUR/MWh -> EUR/kWh
            counts[r["series"]][h] += 1
    return {s: {h: v / counts[s][h] for h, v in d.items()} for s, d in sums.items()}


def _fill(series_by_hour, wanted):
    """Values at the wanted UTC hours; a missing hour takes the same hour a week earlier or later."""
    out = np.empty(len(wanted))
    week = np.timedelta64(168, "h")
    for k, h in enumerate(wanted):
        v = series_by_hour.get(h)
        for step in (week, -week, 2 * week, -2 * week):
            if v is not None:
                break
            v = series_by_hour.get(h - step)
        out[k] = np.nan if v is None else v
    return out


def to_solar_year(series_by_hour, solar_times, year):
    """Price of each solar hour, taken from `year`, keeping weekdays (whole-week shift)."""
    hours = np.asarray(solar_times, dtype="datetime64[h]")
    solar_year = int(hours[0].astype("datetime64[Y]").astype(int)) + 1970
    days = (np.datetime64(f"{year}-01-01") - np.datetime64(f"{solar_year}-01-01")).astype(int)
    weeks = int(round(days / 7))
    shifted = hours + np.timedelta64(weeks * 168, "h")
    return _fill(series_by_hour, shifted)


def solar_year_prices(prices, solar_times, years=YEARS):
    """-> {"pvpc": {year or "typical": array}, "spot": {...}} in EUR/kWh, one value per solar hour."""
    out = {}
    for key, name in (("pvpc", PVPC), ("spot", SPOT)):
        if name not in prices:
            raise SystemExit(f"Series '{name}' is not in the price file. Re-run download_prices.py.")
        per_year = {y: to_solar_year(prices[name], solar_times, y) for y in years}
        per_year["typical"] = np.nanmean(np.vstack(list(per_year.values())), axis=0)
        out[key] = per_year
    return out


def local_hour(times_utc):
    """Local (Madrid) clock hour and weekday (0 = Monday) of UTC times, with real daylight saving."""
    hours, days = [], []
    for t in np.asarray(times_utc, dtype="datetime64[m]"):
        lt = datetime.fromisoformat(str(t)).replace(tzinfo=timezone.utc).astimezone(MADRID)
        hours.append(lt.hour)
        days.append(lt.weekday())
    return np.array(hours), np.array(days)


# --- Tariff periods (what the hours are called on a bill) -----------------------------------
# 2.0TD (supplies up to 15 kW, includes PVPC homes). Source: Selectra PVPC page (docs/SOURCES.md).
# Weekends are always off-peak. National holidays are also off-peak; not modelled here.
def period_2_0td(hour, weekday):
    """'P1' peak, 'P2' mid, 'P3' off-peak."""
    if weekday >= 5 or hour < 8:
        return "P3"
    if 10 <= hour < 14 or 18 <= hour < 22:
        return "P1"
    return "P2"


# 3.0TD (over 15 kW: most offices, schools, hotels). Six periods by season and hour, Peninsula.
# Source: Endesa periods page (docs/SOURCES.md). Seasons (weekdays): high = Jan, Feb, Jul, Dec;
# mid-high = Mar, Nov; mid = Jun, Aug, Sep; low = Apr, May, Oct. Weekends and national holidays = P6.
# For mid and low seasons the page gives peak hours 9-14 and 18-22 and mid hours 8-9, 14-18 and
# 22-24. Its high and mid-high tables do not add up (high lists P1 16-22 and P2 14-18, which
# overlap), so we use the same hours as the other two seasons. CHECK against CNMC Circular 3/2020.
SEASON_3_0TD = {1: "high", 2: "high", 7: "high", 12: "high",
                3: "mid_high", 11: "mid_high",
                6: "mid", 8: "mid", 9: "mid",
                4: "low", 5: "low", 10: "low"}
_PEAK_MID = {"high": ("P1", "P2"), "mid_high": ("P2", "P3"), "mid": ("P3", "P4"), "low": ("P4", "P5")}


def period_3_0td(hour, weekday, month):
    """'P1' (dearest) .. 'P6' (cheapest). Weekends, holidays and 0-8 h are always P6."""
    if weekday >= 5 or hour < 8:
        return "P6"
    peak, mid = _PEAK_MID[SEASON_3_0TD[month]]
    return peak if (9 <= hour < 14 or 18 <= hour < 22) else mid


# NOTE for big buildings: under 3.0TD the bill is (market price + the period's grid fee) per
# kWh, plus a fee per kW of contracted power in each period. The PVPC is not available to
# them. The tool uses the PVPC for everyone for now (team decision, 15 Nov 2026); the period
# functions above are here so a 3.0TD price can be added once we have a real bill.


def summarise(times_utc, sy):
    hours, days = local_hour(times_utc)
    out = {}
    for y, p in sy["pvpc"].items():
        shape = [round(float(np.nanmean(p[hours == h])), 4) for h in range(24)]
        n_days = len(p) // 24
        # evening (19-21 h local) dearer than midday (12-14 h local), day by day
        day_idx = np.arange(len(p)) // 24
        mid = np.array([np.nanmean(p[(day_idx == d) & (hours >= 12) & (hours < 15)]) for d in range(n_days)])
        eve = np.array([np.nanmean(p[(day_idx == d) & (hours >= 19) & (hours < 22)]) for d in range(n_days)])
        key = str(y)
        out[key] = {"pvpc_mean_eur_kwh": round(float(np.nanmean(p)), 4),
                    "pvpc_min_eur_kwh": round(float(np.nanmin(p)), 4),
                    "pvpc_max_eur_kwh": round(float(np.nanmax(p)), 4),
                    "spot_mean_eur_kwh": round(float(np.nanmean(sy["spot"][y])), 4),
                    "pvpc_by_local_hour": shape,
                    "days_evening_dearer_than_midday": int((eve > mid).sum()),
                    "mean_evening_minus_midday_eur_kwh": round(float(np.nanmean(eve - mid)), 4)}
    return out


def write(out_dir, times_utc, sy):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    keys = [(k, y) for k in ("pvpc", "spot") for y in sy[k]]
    with open(out_dir / "prices_hourly_solar_year.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_utc"] + [f"{k}_{y}" for k, y in keys])
        for h, t in enumerate(times_utc):
            w.writerow([str(t) + ":00Z"] + [round(float(sy[k][y][h]), 5) for k, y in keys])
    s = summarise(times_utc, sy)
    (out_dir / "prices_summary.json").write_text(json.dumps(s, indent=2), encoding="utf-8")
    return s


def read_solar_year_prices(path):
    """prices_hourly_solar_year.csv -> same dict as solar_year_prices()."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = {"pvpc": {}, "spot": {}}
    for col in rows[0]:
        if col == "timestamp_utc":
            continue
        kind, y = col.split("_", 1)
        out[kind][int(y) if y.isdigit() else y] = np.array([float(r[col]) for r in rows])
    return out


def main():
    from step04_read_host_demand.host_table import read_hourly
    ap = argparse.ArgumentParser(description="Step 06a: real hourly prices on the solar year")
    ap.add_argument("--prices", default=str(DEFAULT_FILE), help="REE file from download_prices.py")
    ap.add_argument("--solar", default="examples/cep9_hourly.csv",
                    help="any step 03 <name>_hourly.csv (only its hours are used)")
    ap.add_argument("--out", default="data/prices")
    args = ap.parse_args()
    times, _ = read_hourly(args.solar)
    sy = solar_year_prices(read_prices(args.prices), times)
    s = write(args.out, times, sy)
    for y, v in s.items():
        print(f"{y:>8}: PVPC mean {v['pvpc_mean_eur_kwh']:.3f} EUR/kWh (from {v['pvpc_min_eur_kwh']:.3f} "
              f"to {v['pvpc_max_eur_kwh']:.3f}); evening dearer than midday on "
              f"{v['days_evening_dearer_than_midday']} of 365 days")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
