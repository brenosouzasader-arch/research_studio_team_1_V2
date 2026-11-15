# Roofscapes (Re)Powered, V2

IAAC MaAI · Research Studio · team 1: Breno, Sindhuja, Daria

**The question:** should a commercial property owner put solar panels on the whole roof, and can a group of nearby buildings make that investment worth more than using the power alone?

The tool finds how much PV fits on the host roof, predicts when it makes more than the host uses, checks whether a battery at the host is worth it using real hourly Barcelona prices, finds the closest buildings (within about 100 m) that use power at those hours, and runs the panels and battery for all of them hour by hour: first so no solar is wasted, then for the most owner money, and never with a guest paying more than the grid. Its 10 steps follow the team's development roadmap, with one step added for prices and the battery (15 Nov 2026).

By default the tool assumes the guests are wired directly to the host, so it works in other cities too. The Spanish sharing-law options (fixed or hourly shares, RD 244/2019) are kept for comparison.

Every number has a source in [docs/SOURCES.md](docs/SOURCES.md), or is marked **ASSUMPTION** in the code.

V1 (the Eixample co-investment version) stays in [research_studio_team_1](https://github.com/iaac-maai/research_studio_team_1). This repository only has the V1 code that the new tool uses, plus the new steps. [WHAT_CAME_FROM_V1.md](WHAT_CAME_FROM_V1.md) lists every file.

## Folders

```
research_studio_team_1_V2/
├── pipeline/                         all the Python, one folder per roadmap step
│   ├── step01_select_host/           address → building, footprint, Catastro data        (from V1)
│   ├── step02_pv_capacity/           LiDAR roof reading + panel layout → usable m², kWp   (from V1)
│   ├── step03_simulate_generation/   shade + PVGIS → hourly kWh G[h]                      (from V1)
│   ├── step04_read_host_demand/      meter data or proxy → 8,760-hour host table, surplus (new)
│   ├── step05_forecast_demand/       baseline profiles + Open Data BCN; AI model next     (from V1 + to build)
│   ├── step06_prices_and_battery/    real hourly prices, price forecast, battery size     (new)
│   ├── step07_discover_neighbours/   buildings within 100 m → shortlist, closest first    (new, reworked from V1)
│   ├── step08_share_energy/          battery agent for host + guests; legal-share options (new)
│   ├── step09_compare_investment/    owner and guest money, with and without battery      (new)
│   ├── step10_publish_report/        3D view + report                                     (to build)
│   ├── tests/                        offline tests for every step
│   └── examples/                     Bruc 59 example roof + made-up neighbours, for the demo
├── sites/                            one settings file per candidate test site (Poblenou, UPC)
└── docs/SOURCES.md                   every source, and what each one backs up
```

## The test site is still open

Nothing in the code assumes a place. Each candidate site is a file in [sites/](sites/) (Poblenou around the Quatre Cantons school, and UPC Campus Nord). You choose one with `--site`, or by giving the host's address. When the team decides, only the site file and the LiDAR tiles change.

## Quick start

```
cd pipeline
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests                 (should end with "72 passed")
```

**Try steps 04-09 now**, on the Bruc 59 example roof with a made-up office host and made-up neighbours. Step 06 needs the price file once (`download_prices.py`, a few minutes, needs internet); everything else runs offline:

```
python -m step04_read_host_demand.host_table --solar examples\bruc59_hourly.csv --host-kind office --host-floor-m2 300 --building-id demo --out data\host\demo
python step06_prices_and_battery\download_prices.py
python -m step06_prices_and_battery.prices
python -m step06_prices_and_battery.price_model
python -m step06_prices_and_battery.battery_size --host-dir data\host\demo --compare-types --out data\battery\demo
python -m step07_discover_neighbours.candidates --host-dir data\host\demo --lat 41.3935 --lon 2.1689 --candidates-csv examples\demo_candidates.csv --out data\neighbours\demo
python -m step08_share_energy.battery_agent --host-dir data\host\demo --neighbours-dir data\neighbours\demo --out data\sharing\demo
python -m step09_compare_investment.investment --sharing-dir data\sharing\demo --kwp 15.5 --out data\investment\demo
```

What the demo shows (details in each step's README): alone, the office uses 77% of its solar. Two neighbours within 100 m raise that to 97%. A battery is not worth it at an assumed €500/kWh: for the office alone a 5 kWh LFP battery would break even only at about €195/kWh. A better price forecast would add only about €2 a year, because tomorrow's prices are published the day before.

The full run for a real host is in [pipeline/README.md](pipeline/README.md).

## Where it stands (15 Nov 2026)

| Step | Status |
|---|---|
| 01-03 | Working (V1, tested live on Eixample roofs). Needs LiDAR tiles for the new site |
| 04 | Working. Waiting for real meter data; proxy profiles until then |
| 05 | Baseline working. AI model to build in Week 2, only with meter data |
| 06 | Working on real 2023-2025 prices. Battery prices for Europe still an ASSUMPTION; get an installer quote |
| 07 | Working on Catastro and on hand-made lists. Not yet run live |
| 08 | Working, with checks (no grid charging, energy conserved, no guest pays more than the grid). Plans with predicted use only |
| 09 | Working. Panel costs are assumptions |
| 10 | To build (Week 3-4) |
