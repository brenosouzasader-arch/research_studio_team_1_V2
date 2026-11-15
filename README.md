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
│   ├── step07_share_energy/          best group of nearby buildings (one optimiser), battery agent, legal-share options (new)
│   ├── step08_compare_investment/    owner and guest money, with and without battery      (new)
│   ├── step09_publish_report/        one data file for the website                        (new)
│   ├── tests/                        offline tests for every step
│   └── examples/                     CEP9 school example roof and its real neighbours, for the offline tests and demo
├── website/                          the results page (GitHub Pages)
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
python -m pytest tests                 (should end with "86 passed")
```

**Try steps 04-09 now**, on the CEP9 school roof and its real neighbours (building use is an estimate, not meters). Step 06 needs the price file once (`download_prices.py`, a few minutes, needs internet); everything else runs offline:

```
python -m step04_read_host_demand.host_table --solar examples\cep9_hourly.csv --host-kind school --host-floor-m2 1811.7 --building-id cep9 --out data\host\cep9
python step06_prices_and_battery\download_prices.py
python -m step06_prices_and_battery.prices
python -m step06_prices_and_battery.price_model
python -m step06_prices_and_battery.battery_size --host-dir data\host\cep9 --compare-types --out data\battery\cep9
python -m step07_share_energy.optimise --host-dir data\host\cep9 --lat 41.40458605 --lon 2.20067448 --candidates-csv examples\cep9_members.csv --max-distance 2000 --join-rate 1 --out data\match\cep9
python -m step07_share_energy.battery_agent --host-dir data\host\cep9 --neighbours-dir data\match\cep9 --out data\sharing\cep9
python -m step08_compare_investment.investment --sharing-dir data\sharing\cep9 --kwp 53.34 --out data\investment\cep9
```

What it shows (details in each step's README): alone, the school uses 59% of its solar. Its four members (fire station, another institut, a civic centre and 30 homes) raise that to 99%. A battery is not worth it at an assumed €500/kWh. A better price forecast would add only about €3 a year, because tomorrow's prices are published the day before.

The full run for a real host is in [pipeline/README.md](pipeline/README.md).

## Where it stands (15 Nov 2026)

| Step | Status |
|---|---|
| 01-03 | Working (V1, tested live on Eixample roofs). Needs LiDAR tiles for the new site |
| 04 | Working. Waiting for real meter data; proxy profiles until then |
| 05 | Rule-based estimate working. A trained model only with real meter data |
| 06 | Working on real 2023-2025 prices. Battery prices for Europe still an ASSUMPTION; get an installer quote |
| 07 | One optimiser that tries many groups of buildings, in wired (100 m) and Spanish legal (500 m, fixed shares) modes. Run on the 4 real CEP9 members; not yet run on a full Catastro search. The battery agent plans with predicted use only |
| 08 | Working. Panel costs are assumptions |
| 09 | Website working on the demo data (see `website/README.md`). 3D view and the real case still to do |
