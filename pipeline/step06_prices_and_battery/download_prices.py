"""Download Spanish electricity prices for the battery step (run on your laptop).

    pip install requests OMIEData pandas
    python download_prices.py

Writes into data/prices/ (next to where you run it):
- pvpc_hourly.csv   REE: the regulated PVPC price, every hour, 2023-2025 (EUR/MWh)
- omie_hourly.csv   OMIE: the day-ahead market price for Spain, 2023-2025 (EUR/MWh)

It takes a few minutes. If one part fails, the other still runs. Send Claude the
printed messages if anything goes wrong.
"""
import datetime as dt
import json
import time
from pathlib import Path

import requests

OUT = Path("data/prices")
OUT.mkdir(parents=True, exist_ok=True)
START, END = dt.date(2023, 1, 1), dt.date(2025, 12, 31)
REE = "https://apidatos.ree.es/es/datos/mercados/precios-mercados-tiempo-real"


def months(a, b):
    d = a.replace(day=1)
    while d <= b:
        nxt = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        yield d, min(nxt - dt.timedelta(days=1), b)
        d = nxt


def ree_pvpc():
    rows = []
    for a, b in months(START, END):
        params = {"start_date": f"{a}T00:00", "end_date": f"{b}T23:59", "time_trunc": "hour"}
        for attempt in range(3):
            try:
                r = requests.get(REE, params=params, timeout=60)
                r.raise_for_status()
                break
            except requests.RequestException as e:
                print(f"REE {a:%Y-%m} attempt {attempt + 1} failed: {e}")
                time.sleep(3)
        else:
            continue
        for series in r.json().get("included", []):
            name = series.get("attributes", {}).get("title", "")
            for v in series.get("attributes", {}).get("values", []):
                rows.append((v["datetime"], name, v["value"]))
        print(f"REE {a:%Y-%m}: ok")
        time.sleep(0.5)
    with open(OUT / "pvpc_hourly.csv", "w", encoding="utf-8") as f:
        f.write("datetime,series,eur_mwh\n")
        for t, n, v in rows:
            f.write(f"{t},{n},{v}\n")
    print(f"-> {OUT / 'pvpc_hourly.csv'} ({len(rows)} rows; series: {sorted({n for _, n, _ in rows})})")


def omie():
    from OMIEData.DataImport.omie_marginalprice_importer import OMIEMarginalPriceFileImporter
    df = OMIEMarginalPriceFileImporter(date_ini=dt.datetime.combine(START, dt.time()),
                                       date_end=dt.datetime.combine(END, dt.time())).read_to_dataframe(verbose=True)
    df.to_csv(OUT / "omie_hourly.csv", index=False)
    print(f"-> {OUT / 'omie_hourly.csv'} ({len(df)} rows)")


if __name__ == "__main__":
    for job in (ree_pvpc, omie):
        try:
            job()
        except Exception as e:  # keep going with the other source
            print(f"{job.__name__} failed: {e}")
