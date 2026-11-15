# Step 09: Publish report

**Question this step answers:** how do we show the results so anyone can check them?

`export_site_data.py` collects the outputs of steps 03 to 09 and `docs/SOURCES.md` into one file, `website/data/site_data.json`, which the website in [`../../website/`](../../website/) reads. Every headline number in it carries a label: *measured* (real prices or meters), *modelled* (computed by the pipeline) or *assumption* (a value we chose), and where it comes from.

The website shows the **CEP9 school (Institut Quatre Cantons, Poblenou)**. To rebuild it, run from `pipeline\` (steps 01-03 need internet and the LiDAR sheets 433583 and 433584; the rest runs offline):

```
python -m step03_simulate_generation.shade_yield "Camí Antic de València 35, Barcelona" --laz-dir data\lidar --layout neat --out data\pv\cep9
python -m step04_read_host_demand.host_table --solar data\pv\cep9_hourly.csv --host-kind school --host-floor-m2 1811.7 --building-id cep9 --out data\host\cep9
python -m step06_prices_and_battery.battery_size --host-dir data\host\cep9 --compare-types --out data\battery\cep9
python -m step07_share_energy.candidates --host-dir data\host\cep9 --lat 41.40458605 --lon 2.20067448 --candidates-csv examples\cep9_members.csv --max-distance 2000 --join-rate 1 --out data\neighbours\cep9
python -m step07_share_energy.battery_agent --host-dir data\host\cep9 --neighbours-dir data\neighbours\cep9 --prices-dir data\prices --out data\sharing\cep9
python -m step07_share_energy.agreed_shares --host-dir data\host\cep9 --neighbours-dir data\neighbours\cep9 --shares host=0.30,homes_30=0.232 --guest-price 0 --out data\agreed\cep9
python -m step08_compare_investment.investment --sharing-dir data\sharing\cep9 --kwp 53.34 --out data\investment\cep9
python -m step09_publish_report.export_site_data --name cep9 --yield data\pv\cep9_yield.json --label "CEP9 school roof, Poblenou" --host-label "Institut Quatre Cantons" --host-kind school --max-distance 2000 --lat 41.40458605 --lon 2.20067448 --note "..." --reach-note "..." --host-use-note "..." --actual examples\cep9_actual.json
```

Why these values (all ASSUMPTIONS unless marked):
- `--host-floor-m2 1811.7`: x 60 kWh/m2 = 108,700 kWh a year, the 2018 average of Barcelona's municipal institutes [Consums Energètics Edificis 2008-2018]. (Catastro's 3 floors x 1,422.5 m2 x 60 kWh/m2 would give 256,000.) "The school keeps 30%" [The Guardian] is CEP9's agreed share, not how much the school uses itself; it is the `host=0.30` share in `agreed_shares`.
- `examples\cep9_members.csv`: the real CEP9 members [CEP9 presentation]; yearly use = 2018 average of that building type [Consums Energètics Edificis 2008-2018], homes by our step 05 rule; two positions not checked.
- `agreed_shares`: CEP9's own terms, fixed shares and free power, shown next to our tool's terms on the money section.
- `--max-distance 2000`: CEP9's own 2 km radius [CEP9 presentation], instead of the tool's 100 m.
- `--layout neat` (420 W): 127 panels, 53.3 kWp, closest to the real 108 x 540 W = 58.32 kWp.


It needs these folders from the earlier steps: `data\host\<name>` (04), `data\prices` (06), `data\battery\<name>` (06), `data\neighbours\<name>` (07), `data\sharing\<name>` (08), `data\investment\<name>` (09).

What the website shows: the roof and its monthly solar, spare solar for every hour of the year, the buildings within 100 m and their daily use, real hourly prices and the forecast test, the battery sizes and types with an example day run by the battery agent, and the owner's money with a **guest-discount slider** (default 10%, team decision 15 Nov 2026). How to view and publish it: [`website/README.md`](../../website/README.md).

Still to add: a 3D view (V1's ArcGIS map is in the V1 repository) and the real A160 case.
