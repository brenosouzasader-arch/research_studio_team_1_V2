# The pipeline

Run every command **from this folder**. Each step folder has its own README with inputs, outputs and commands.

| Step | Folder | Question it answers | Where it gets its information (inputs) | Method | Principal sources | Main output |
|---|---|---|---|---|---|---|
| 01 Select host | `step01_select_host/` | Which building, how big, what use? | An address or a map point; Catastro; ICGC geocoder; LiDAR tiles; optional heritage layer | Lookups in public services, plus a rule (flat-roof check: 70% of LiDAR cells under 5° slope) | Catastro INSPIRE; ICGC geocoder and LiDAR (CC BY 4.0) | refcat, footprint, height, use, dwellings |
| 02 PV capacity | `step02_pv_capacity/` | How much of the roof can hold panels? | Step 01 footprint; ICGC LiDAR; ICGC orthophoto (picture only) | Rules on LiDAR heights (obstacles, edge and obstacle setbacks); row direction rule or search | ICGC LiDAR Territorial 2021-2023; team's panel size and setback assumptions | usable m², obstacles, layout |
| 03 Generation | `step03_simulate_generation/` | How much solar, every hour of the year? | Step 02 usable area; LiDAR shade horizon within 150 m; PVGIS typical-year weather | Formulas (sun position, shade geometry, panel and heat model) and a block-picking rule for neat layouts | PVGIS (EU JRC); assumptions for losses and heat | panels, kWp, hourly kWh G[h] for 6 layouts |
| 04 Host demand | `step04_read_host_demand/` | How much does the host use, what is left over? | Step 03 hourly solar; the host's meter if we have it, else floor area and use type | Measured data, or an **estimate** from rules (never a prediction yet) | Meters (none yet); Consums Energètics Edificis 2008-2018 for the CEP9 case | `host_table.csv`: G, D[host], used, surplus |
| 05 Demand profiles | `step05_forecast_demand/` | How much do buildings without meters use? | Catastro (dwellings, floor area, use); Open Data BCN electricity by area | Rules and statistics (**not AI yet**; a trained model only with real meters) | Open Data BCN; Consums Energètics Edificis 2008-2018 | hourly use profiles |
| 06 Prices and battery | `step06_prices_and_battery/` | What does power cost each hour, is a battery worth it? | REE hourly PVPC and wholesale prices 2023-2025; steps 04-05 use; battery numbers | **Machine learning** for the price forecast (gradient-boosted trees); **linear programming** for the battery controller; formulas for size and cost | REE REData; OMIE; NREL ATB 2024; PNNL 2022; battery price is an ASSUMPTION | `prices_hourly_solar_year.csv`, `price_model_report.json`, `battery_sizing.json` |
| 07 Match and share | `step07_share_energy/` | Which group of buildings should share the roof, and who gets the solar each hour? | Step 04 surplus; every building within reach (Catastro or a list) with step 05 use; step 06 prices | **Optimisation**: tries many combinations of buildings (all of them, or a local search) and keeps the one that uses the most solar; then a linear program runs the battery. Two modes: wired 100 m, or Spanish legal fixed shares 500 m | RD 244/2019 (BOE); CEP9 presentation; REE prices | `match_summary.json`, `battery_agent_summary.json`, `allocation.csv` |
| 08 Investment | `step08_compare_investment/` | What does the owner earn, when does it pay back? | Step 07 results; panel and battery costs; prices | Formulas (simple payback) | APPA 2024 and NREL ATB 2024 (cost checks); several costs are ASSUMPTIONS | `investment_battery.json`, `investment_summary.json` |
| 09 Publish report | `step09_publish_report/` | How do we show it so anyone can check it? | Outputs of steps 01-09; `docs/SOURCES.md` | Collects and labels numbers (measured, modelled, assumption, reported) | docs/SOURCES.md | `website/data/site_data.json` |

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

Example with the CEP9 school (Institut Quatre Cantons, Poblenou). It needs LiDAR sheets 433583 and 433584 in `data\lidar`. Steps 01-03 need internet (from a laptop); the rest runs offline once the price file is downloaded.

```
python -m step01_select_host.find_building "Camí Antic de València 35, Barcelona" --laz-dir data\lidar
python -m step02_pv_capacity.read_roof "Camí Antic de València 35, Barcelona" --laz-dir data\lidar --out data\pv\cep9
python -m step03_simulate_generation.shade_yield "Camí Antic de València 35, Barcelona" --laz-dir data\lidar --usable data\pv\cep9_usable.geojson --layout neat --orient search --out data\pv\cep9
python -m step04_read_host_demand.host_table --solar data\pv\cep9_hourly.csv --host-kind school --host-floor-m2 1811.7 --building-id cep9 --out data\host\cep9
python step06_prices_and_battery\download_prices.py
python -m step06_prices_and_battery.prices
python -m step06_prices_and_battery.price_model
python -m step06_prices_and_battery.battery_size --host-dir data\host\cep9 --compare-types --out data\battery\cep9
python -m step07_share_energy.optimise --host-dir data\host\cep9 --lat 41.40458605 --lon 2.20067448 --candidates-csv examples\cep9_members.csv --mode wired --max-distance 2000 --join-rate 1 --out data\match\cep9
python -m step07_share_energy.battery_agent --host-dir data\host\cep9 --neighbours-dir data\match\cep9 --out data\sharing\cep9
python -m step08_compare_investment.investment --sharing-dir data\sharing\cep9 --kwp <kWp from data\pv\cep9_yield.json> --out data\investment\cep9
```

The last step (publishing the website data) is in [step10's README](step09_publish_report/README.md).

No meter file yet? That is the situation today: use `--host-kind` and `--host-floor-m2` as above. With one, replace them with `--metered data\meters\cep9.csv`.

## Open questions for the team (15 Nov 2026)

1. **Panel cost**: now €1,061 per kWp (Marblanc Solar, homes under 20 kW), with €730 (APPA 2024, 180 kW roof) as best case. A quote for a roof of this size from a Barcelona installer would settle it.
2. **Battery price**: a Barcelona installer quote for 20-100 kWh LFP (the only checkable price we have is UK and in pounds).
3. **Building demand**: which source for hourly use by building type? GoiEner (Spain, hourly, includes offices and public buildings, not Barcelona) or something from Madrid (we have not found one).
4. **Google Solar**: a screenshot of the same roof, for the comparison on the website.
5. **Meters**: ask CEP9 / the school for real hourly use.

## Where outputs go

Into `data\` (ignored by git). Put results worth sharing in `examples\`.
