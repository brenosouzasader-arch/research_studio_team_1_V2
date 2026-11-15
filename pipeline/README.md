# The pipeline

Run every command **from this folder**. Each step folder has its own README with inputs, outputs and commands.

| Step | Folder | Question it answers | Main output |
|---|---|---|---|
| 01 Select host | `step01_select_host/` | Which building, how big, what use? | refcat, footprint, height, use, dwellings |
| 02 Evaluate PV capacity | `step02_pv_capacity/` | How much of the roof can hold panels? | usable m², obstacles, layout |
| 03 Simulate generation | `step03_simulate_generation/` | How much solar, every hour of the year? | panels, kWp, hourly kWh G[h] |
| 04 Read host demand | `step04_read_host_demand/` | How much does the host use, and what is left over? | `host_table.csv`: G, D[host], self-consumed, surplus |
| 05 Forecast demand | `step05_forecast_demand/` | How much do buildings without meters use? | hourly use profiles |
| 06 Prices and battery | `step06_prices_and_battery/` | What does power cost each hour, and is a battery worth it? | `prices_hourly_solar_year.csv`, `price_model_report.json`, `battery_sizing.json` |
| 07 Discover neighbours | `step07_discover_neighbours/` | Which buildings within 100 m could use the surplus? | `shortlist.csv`, `candidate_buildings.geojson` |
| 08 Share energy | `step08_share_energy/` | Hour by hour, who gets the solar and the battery's power? | `battery_agent_summary.json`, `decisions_hourly.csv` (and `allocation.csv` for the legal options) |
| 09 Compare investment | `step09_compare_investment/` | What does the owner earn, and when does it pay back? | `investment_battery.json`, `investment_summary.json` |
| 10 Publish report | `step10_publish_report/` | How do we show it so anyone can check it? | `website/data/site_data.json` for the website |

Every number the tool uses has a source in [../docs/SOURCES.md](../docs/SOURCES.md) or is marked **ASSUMPTION** in the code.

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
python step06_prices_and_battery\download_prices.py
python -m step06_prices_and_battery.prices
python -m step06_prices_and_battery.price_model
python -m step06_prices_and_battery.battery_size --host-dir data\host\nexus2 --compare-types --out data\battery\nexus2
python -m step07_discover_neighbours.candidates --host-dir data\host\nexus2 --host "Carrer de Jordi Girona 29, Barcelona" --out data\neighbours\nexus2
python -m step08_share_energy.battery_agent --host-dir data\host\nexus2 --neighbours-dir data\neighbours\nexus2 --out data\sharing\nexus2
python -m step09_compare_investment.investment --sharing-dir data\sharing\nexus2 --kwp <kWp from data\pv\nexus2_yield.json> --out data\investment\nexus2
python -m step10_publish_report.export_site_data --name nexus2 --yield data\pv\nexus2_yield.json --lat <host lat> --lon <host lon>
```

No meter file yet? Replace `--metered ...` with `--host-kind office --host-floor-m2 6000`.

## Where outputs go

Into `data\` (ignored by git). Put results worth sharing in `examples\`.
