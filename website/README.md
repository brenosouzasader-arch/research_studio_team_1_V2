# Website

The results page for the tool: one page, one section per question, every number tagged *measured*, *modelled* or *assumption* with its source.

- `index.html`, `styles.css`, `app.js`: the page. Plain HTML, CSS and JavaScript, no build step. Charts are drawn as SVG by `app.js`.
- `data/site_data.json`: everything the page shows. **Don't edit it by hand.** It is written by the pipeline.

## Update the numbers

After running steps 03 to 09 for a case (see `pipeline/README.md`), from the `pipeline` folder:

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


`--name` is the folder name you used in `data\host\<name>`, `data\sharing\<name>` and so on. `--lat --lon` are the host's position (the same as in step 07). Then commit `website/data/site_data.json` and push.

## See it on your laptop

```
cd website
python -m http.server 8000
```

Open http://localhost:8000. (Opening `index.html` by double-click doesn't work, because the browser won't load the data file that way.)

## Online

`.github/workflows/pages.yml` publishes this folder on GitHub Pages each time `main` changes. It needs one switch, once: on GitHub, **Settings → Pages → Build and deployment → Source: GitHub Actions**. The address is then https://brenosouzasader-arch.github.io/research_studio_team_1_V2/.

## What the page does itself

Only the guest-discount slider does any maths, using the same formula as step 08 (`owner_total_at_discount`): owner = host savings + (1 − discount) × guests' solar at grid price + export. Everything else is read from the data file.
