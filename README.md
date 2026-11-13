# Roofscapes (Re)Powered, V2

IAAC MaAI · Research Studio · team 1: Breno, Sindhuja, Daria

**The question:** should a commercial property owner put solar panels on the whole roof, and can a group of nearby buildings make that investment worth more than using the power alone?

The tool finds how much PV fits on the host roof, predicts when it makes more than the host uses, finds nearby buildings that use power at those hours, and compares sharing agreements (fixed or hourly shares, RD 244/2019) with keeping it all. It follows the team's roadmap in [docs/roadmap-track-2.pdf](docs/roadmap-track-2.pdf).

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
│   ├── step06_discover_neighbours/   nearby buildings → shortlist of 3-5 by fit           (new, reworked from V1)
│   ├── step07_optimize_allocation/   host-only vs fixed vs hourly betas                   (new)
│   ├── step08_compare_investment/    owner and participant money, low/central/high        (new)
│   ├── step09_publish_report/        3D view + report                                     (to build)
│   ├── tests/                        offline tests for every step
│   └── examples/                     real outputs to try things without internet
├── sites/                            one settings file per candidate test site (Poblenou, UPC)
├── prototypes/                       post-midterm quick tests, kept for reference
└── docs/                             roadmap, test-site research, recommendations
```

## The test site is still open

Nothing in the code assumes a place. Each candidate site is a file in [sites/](sites/) (Poblenou around the Quatre Cantons school, and UPC Campus Nord). You choose one with `--site`, or by giving the host's address. When the team decides, only the site file and the LiDAR tiles change.

## Quick start

```
cd pipeline
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests                 (should end with "45 passed")
```

**Try steps 04-08 now, without internet**, on the Bruc 59 example roof with a made-up office host and made-up neighbours:

```
python -m step04_read_host_demand.host_table --solar examples\bruc59_hourly.csv --host-kind office --host-floor-m2 300 --building-id demo --out data\host\demo
python -m step06_discover_neighbours.candidates --host-dir data\host\demo --lat 41.3935 --lon 2.1689 --candidates-csv examples\demo_candidates.csv --out data\neighbours\demo
python -m step07_optimize_allocation.allocation --host-dir data\host\demo --neighbours-dir data\neighbours\demo --out data\allocation\demo
python -m step08_compare_investment.investment --allocation-dir data\allocation\demo --kwp 15.5 --out data\investment\demo
```

The full run for a real host is in [pipeline/README.md](pipeline/README.md).

## Where it stands (13 Nov 2026)

| Step | Status |
|---|---|
| 01-03 | Working (V1, tested live on Eixample roofs). Needs LiDAR tiles for the new site |
| 04 | Working. Waiting for real meter data; proxy profiles until then |
| 05 | Baseline working. AI model to build in Week 2, only with meter data |
| 06 | Working on Catastro and on hand-made lists. Not yet run live |
| 07-08 | Working, with checks. Prices are assumptions |
| 09 | To build (Week 3-4) |
