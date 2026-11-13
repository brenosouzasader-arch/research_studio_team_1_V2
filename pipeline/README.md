# The pipeline

Run every command **from this folder**. Each step folder has its own README with inputs, outputs and commands.

| Roadmap step | Folder | Gives |
|---|---|---|
| 01 Select host | `step01_select_host/` | refcat, footprint, height, use, dwellings |
| 02 Evaluate PV capacity | `step02_pv_capacity/` | usable m², obstacles, layout |
| 03 Simulate generation | `step03_simulate_generation/` | panels, kWp, hourly kWh G[h] |
| 04 Read host demand | `step04_read_host_demand/` | `host_table.csv`: G, D[host], self-consumed, surplus |
| 05 Forecast demand | `step05_forecast_demand/` | hourly use for buildings without meters |
| 06 Discover neighbours | `step06_discover_neighbours/` | `candidate_buildings.geojson`, shortlist |
| 07 Optimize allocation | `step07_optimize_allocation/` | `allocation.csv`, betas per scenario |
| 08 Compare investment | `step08_compare_investment/` | `investment_summary.json` |
| 09 Publish report | `step09_publish_report/` | to build |

`sites.py` reads the test-site files in `../sites/`.

## Setup (once)

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests
python smoke_test.py                                   (live check of step 01 against Catastro and ICGC)
python -m step03_simulate_generation.weather --site upc_campus_nord
```

Download the ICGC LiDAR tiles (LAZ) for your site into `data\lidar\`.

## A real host, start to end

Example with Nexus II (UPC). Swap the address and site for Poblenou.

```
python -m step02_pv_capacity.read_roof "Carrer de Jordi Girona 29, Barcelona" --laz-dir data\lidar --out data\pv\nexus2
python -m step03_simulate_generation.shade_yield "Carrer de Jordi Girona 29, Barcelona" --laz-dir data\lidar --usable data\pv\nexus2_usable.geojson --out data\pv\nexus2
python -m step05_forecast_demand.bcn_data --site upc_campus_nord
python -m step04_read_host_demand.host_table --solar data\pv\nexus2_hourly.csv --metered data\meters\nexus2.csv --building-id nexus2 --out data\host\nexus2
python -m step06_discover_neighbours.candidates --host-dir data\host\nexus2 --host "Carrer de Jordi Girona 29, Barcelona" --out data\neighbours\nexus2
python -m step07_optimize_allocation.allocation --host-dir data\host\nexus2 --neighbours-dir data\neighbours\nexus2 --out data\allocation\nexus2
python -m step08_compare_investment.investment --allocation-dir data\allocation\nexus2 --kwp <kWp from data\pv\nexus2_yield.json> --out data\investment\nexus2
```

No meter file yet? Replace `--metered ...` with `--host-kind office --host-floor-m2 6000`.

## Where outputs go

Into `data\` (ignored by git). Put results worth sharing in `examples\`.
