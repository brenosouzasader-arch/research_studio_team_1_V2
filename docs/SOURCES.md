# Sources and what each one backs up

Roofscapes (Re)Powered V2, 15 November 2026. Every figure the tool or the team quotes should point to a line here, so anyone can check it. Numbers without a source are marked **ASSUMPTION** in the code and listed at the end. In the code and READMEs, a short name in square brackets, such as [NREL ATB], points to a row below.

**How to check a number:** find its short name in the code comment or README, open the link in that row, and look for the quoted words.

## Electricity prices

| Source | What it backs up |
|---|---|
| **[Forbes España]** [Forbes España, 30 Sep 2025: the wholesale market moves to quarter-hour trading](https://forbes.es/economia/805739/el-mercado-mayorista-de-la-luz-estrena-la-negociacion-cuarto-horaria-con-precios-de-667-a-230-euros-mwh/) | The Spanish day-ahead market (OMIE) sets a price every 15 minutes from 1 Oct 2025. Example spread on that day: €6.67/MWh at 15:00 to €230/MWh at 21:00. Forward-market share of PVPC: 25% (2024), 40% (2025), 55% (2026). |
| [Merca2, 18 Oct 2026](https://www.merca2.es/2026/10/18/precio-luz-minimo-54-dias-2475984/) | Typical daily shape: cheapest at midday (solar), most expensive after sunset (gas). Day average €76.28/MWh with a night peak of €182/MWh. |
| **[Selectra PVPC]** [Selectra: PVPC explained (updated 15 Nov 2026)](https://selectra.es/energia/info/pvpc) | PVPC is set by the government, not by retailers, and follows the wholesale and forward markets. It's for supplies under 10 kW. Home time bands (2.0TD): peak 10-14h and 18-22h, mid 8-10h, 14-18h and 22-24h, off-peak 0-8h, weekends and holidays. Example day range €0.054 to €0.241/kWh. |
| **[Endesa periods]** [Endesa: 3.0TD / 6.xTD time periods, Peninsula](https://www.endesa.com/es/comunicacion/cartera/peajes-empresas-asesoramiento/periodos-horarios/peninsula) | Big buildings (over 15 kW) pay grid fees in 6 periods (P1 to P6) by season and hour. Seasons on weekdays: high = Jan, Feb, Jul, Dec; mid-high = Mar, Nov; mid = Jun, Aug, Sep; low = Apr, May, Oct. "Sábados, Domingos y festivos nacionales": P6 all day. Mid season: P3 9-14h and 18-22h, P4 8-9h, 14-18h and 22-24h; low season the same with P4/P5; 0-8h always P6. **Caution:** the page's high and mid-high tables contradict themselves (high lists "P1: 9:00h - 14:00h, 16:00h - 22:00h" and "P2: ... 14:00h - 18:00h", which overlap), so `prices.py` uses the mid/low hour pattern for every season. To check against CNMC Circular 3/2020. Used by `prices.period_3_0td`. |
| **[OMIE]** [OMIE: the electricity market](https://www.omie.es/es/mercado-de-electricidad) | "Todos los días del año a las 12:00 CET, se lleva a cabo la sesión del mercado diario" that sets the prices for the 24 hours of the next day. So tomorrow's prices are known before tomorrow starts. |
| **[Modo Energy]** [Modo Energy, 23 Apr 2026: Spain's market sequence](https://modoenergy.com/research/es/spain-bess-market-sequence-omie-ree) | Day-ahead gate closure 12:00 CET; "Los resultados finales se publican aproximadamente a las 12:57"; 15-minute periods (96 a day) since 1 Oct 2025. A third-party explainer, not OMIE itself. |
| **[REE]** [REE REData API](https://www.ree.es/es/apidatos) | Free source of past hourly market data, no key needed. `download_prices.py` gets two series from it for 2023-2025: "PVPC" (26,304 hourly values, complete) and "Precio mercado spot" (the OMIE day-ahead price). This file is the price input of the whole tool (`data/prices/pvpc_hourly.csv`). |
| [OMIEData (Python package)](https://pypi.org/project/OMIEData) | Downloads OMIE's public daily price files (`omie_hourly.csv`, one row per day and price type). Used only as a cross-check: **our check (15 Nov 2026)** found the REE "Precio mercado spot" equal to OMIE's Spanish price to the cent in 99.7% of 24,090 hours (Jan 2023 to Sep 2025); the others are clock-change days. |
| [Hugging Face: hsilvosa/omie-electricity](https://huggingface.co/datasets/hsilvosa/omie-electricity) | Ready-made Spanish day-ahead prices, Jan 2023 to Aug 2026 (hourly, 15-minute from Oct 2025). Backup source; older versions had broken decimals. |
| [Ajuntament de Barcelona via sostenible.cat, Feb 2023](https://www.sostenible.cat/print/article/mes-de-tres-cents-centres-educatius-es-connecten-a-barcelona-energia) | 341 Barcelona education centres (all 161 primary schools, 103 nurseries) buy their power from Barcelona Energia, the city's own supplier. 32 have PV. No tariff is published, which is why we default to PVPC. |

## Prices we computed ourselves from the REE file

These come from `python -m step06_prices_and_battery.prices` and `price_model`, and anyone can re-run them.

| Figure | Value | Output file |
|---|---|---|
| PVPC yearly mean | 2023: €0.147/kWh, 2024: €0.127, 2025: €0.137 | `prices_summary.json` |
| Typical daily shape (mean of 2023-2025) | cheapest about €0.094-0.095/kWh at 14-16h local, dearest about €0.204-0.206 at 20-22h | `prices_summary.json`, `pvpc_by_local_hour` |
| Days with the evening (19-22h) dearer than midday (12-15h) | 365, 362 and 364 of 365 (2023, 2024, 2025) | `prices_summary.json` |
| Price forecast error on 2025, 2 days ahead | model €0.0203/kWh, same hour last week €0.0250, typical year €0.0225 | `price_model_report.json` |

## Batteries

| Source | What it backs up |
|---|---|
| **[NREL ATB 2024]** [NREL Annual Technology Baseline 2024: commercial battery storage](https://atb.nrel.gov/electricity/2024/commercial_battery_storage) | Lithium-ion (LFP and NMC), "with LFP becoming the primary chemistry for stationary storage starting in 2021". "85% as a representative round-trip efficiency". "15-year lifetime". About one cycle a day. Fixed O&M "2.5% of the capital costs". Systems of 100-2,000 kW, 1-8 hours. Gives pack prices only (e.g. 4-hour $199/kWh, 2022 USD), not a full installed price we could use. |
| **[PNNL 2022]** Viswanathan et al., [2022 Grid Energy Storage Technology Cost and Performance Assessment](https://www.energy.gov/cmei/2022-grid-energy-storage-technology-cost-and-performance-assessment) (PNNL-33283; [PDF](https://www.sandia.gov/app/uploads/sites/256/2024/02/ESGC-Cost-Performance-Report-2022-PNNL-33283.pdf)) | "the cycle life at 80% DOD for LFP and NMC is 2,400 and 1,520 cycles, respectively"; calendar lives "of 16 years for LFP and 13 years for NMC". Installed cost at 100 MW: 4 hours LFP $385/kWh, NMC $435/kWh; 10 hours LFP $356/kWh, vanadium flow $385/kWh. We use only the **ratios** between types, because these are utility-size plants. |

Battery price (chosen by Breno, 15 Nov 2026): the only price we could read is one shop listing, [Lithium Battery Deye SE-G5.1 Pro-B on tienda-solar.es](https://tienda-solar.es/en/inicio/2025-bateria-de-litio-deye-se-g51-pro-b-512kwh): €999.00 "Tax included", 5.12 kWh nominal, 4.6 kWh usable, so €195 per nominal kWh. It backs the LFP price in `battery_types.py`. It is a home unit without installation or inverter, so for a 20-500 kWh building it stays an ASSUMPTION until we get an installer quote. The shop's category page lists no products to our fetch tool, so no average over several products was possible. [Endesa Solar Plus & Batería Virtual](https://www.endesa.com/en/catalog/solar-catalogue/endesa-solar-plus-bateria-virtual) ("last price and terms update: October 15, 2026") sells a *virtual* battery at €2 a month. It is a euro balance of surplus, not kWh of storage, so it gives no €/kWh price; we use its surplus price (0,06 €/kWh excluding taxes) as the export price. The page contradicts itself on whether the €2 includes taxes.

## Surplus: do schools and offices use all their solar?

| Source | What it backs up |
|---|---|
| [CEP9 Poblenou energy community presentation](https://elpoblenou.cat/wp-content/uploads/2024/10/presentacio-CEP9_v2.pptx.pdf) | Quatre Cantons school roof: 58.32 kWp, 108 panels, about 73,750 kWh/yr. It is shared with Institut Quatre Cantons, Institut Maria Espinalt, Can Felipa, the Llevant fire station and 30 homes (400-700 kWh/yr each, saving €120-140), within a 2 km radius, energy given for free. The city studied 13 roofs and built 1. |
| **[Consums Energètics Edificis 2008-2018]** [Ajuntament de Barcelona, energy use of municipal buildings (Feb 2020)](https://bcnroc.ajuntament.barcelona.cat/jspui/bitstream/11703/129947/3/Consums%20Energ%c3%a8tics%20Edificis%202008-2018.pdf.txt) | Measured 2018 electricity by building type. Our averages (total ÷ buildings): institut 6,631,491 kWh / 61 = about 108,700 kWh; school (CEIP) 10,463,055 / 128 = about 81,700; civic centre and similar 16,419,643 / 193 = about 85,100; fire station 1,382,535 / 8 = about 172,800. Used as CEP9 members' yearly use. No floor areas, so no kWh/m². |
| [Sant Martí services guide, Dec 2020](https://bcnroc.ajuntament.barcelona.cat/jspui/bitstream/11703/117042/6/Guia_Equipaments_SantMart%c3%ad_barris_2020-12.pdf.txt) | Addresses: Institut Maria Espinalt, Camí Antic de València 82; Parc de Bombers de Llevant, Castella 6. |
| [Barcelona Cultura: Centre Cívic Can Felipa](https://barcelona.cat/barcelonacultura/en/detail/centre-civic-can-felipa_92086035490) | Can Felipa address, Plaça de Josep Maria Huertas Claveria 1. |
| [The Guardian, 25 Jul 2022 (via PressReader)](https://www.pressreader.com/usa/the-guardian-usa/20220725/281711208390346) | The Quatre Cantons school keeps about 30% of its roof's output and the community gets the rest. The city paid about €94,000. Evidence that schools have surplus. |
| [UPC SIRENA global report 2025](https://sostenible.upc.edu/ca/reptes/documents-pla-2030/informe-sirena-global-2025.pdf) | Campus Diagonal Nord teaching buildings (Aularis) have 170 + 80.18 kWp with 50% self-consumption. UPC's PV is 2.17% of its total use. SIRENA data is published only as yearly reports. |
| [Acciona: SelvaMar business campus](https://www.acciona.com) (as cited in the team's test-site research) | 852 panels, 315.24 kWp, covering 18% of the office building's use. Evidence that big offices use all their own solar. Exact page to be linked. |
| [betevé, 27 Aug 2025: panels on Sants and Sant Antoni markets](https://beteve.cat/medi-ambient/mercat-sants-sant-antoni-estrenen-plaques-fotovoltaiques/) | Mercat de Sants uses about 91% of its output on site and Sant Antoni 100%. Evidence that markets (with fridges) have almost no surplus. 17 markets have panels; the goal is 31. |
| Madrigal, Gallinad, Vicario, Morell & Vilanova (2026). *Improving energy distribution in collective self-consumption via XGBoost-based allocation coefficients prediction*. Applied Energy 409, 127469. [doi:10.1016/j.apenergy.2026.127469](https://doi.org/10.1016/j.apenergy.2026.127469) (open access, CC BY) | A real municipal community in Barcelona province with two school hosts (140 and 86 kWp). XGBoost predicts hourly use from the calendar plus use 1 hour, 24 hours and 1 week earlier, then sets hourly shares: +8.4% local use, -34% surplus, up to -30% grid use. Supports schools as hosts and our step 05/08 method. It has no battery and its data is not shared. |

## Datasets we could use for building demand (step 04-05), and for heritage (step 01)

| Source | What it backs up |
|---|---|
| [GoiEner smart meters data, Scientific Data 2024](https://www.nature.com/articles/s41597-023-02846-0) (DOI [10.5281/zenodo.7362094](https://doi.org/10.5281/zenodo.7362094)) | 25,559 Spanish electricity supply points with HOURLY demand, late 2014 to June 2022, licence CC BY 4.0. About 81% homes, the rest retail, offices, industry and public buildings. Mostly the Basque Country (72.5%), Navarre (13.8%) and Madrid (4.4%), so not Barcelona. The best open hourly demand data for Spain that we found. Not used yet |
| [Open Data BCN: protected architectural heritage](https://opendata-ajuntament.barcelona.cat/data/en/dataset/patrimoni-arquitectonic-protegit) | The city's heritage catalogue exists as open data (CC BY 4.0, first published 10 Oct 2019, 3 resources). The page names WMS only; formats and fields (cadastral reference? protection level?) still to be checked. Would fill step 01's `heritage_protected` flag |
| [PVGIS non-interactive API](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/getting-started-pvgis/api-non-interactive-service_en) | `loss` ("sum of system losses, in percent") is a required input with no default; the page's example uses 14. Gives no temperature coefficient |
| [APPA Renovables, Informe Autoconsumo Fotovoltaico 2024](https://static.smartgridsinfo.es/media/2025/02/Informe-Autoconsumo-Fotovoltaico-2024.pdf) | A typical 180 kW industrial installation costs €131,400 without taxes (p. 13), about €730 per kWp |
| [NREL ATB 2024: commercial PV](https://atb.nrel.gov/electricity/2024/commercial_pv) | US commercial PV: US$1.78 per W in 2023; fixed upkeep about US$19 per kW a year |
| [Reonic: commercial battery storage cost UK 2026](https://reonic.com/en-gb/blog/commercial-battery-storage-cost/) | UK, in pounds: about £200-800 per kWh installed depending on size (the page contradicts itself for 50 and 100 kWh). Too wide and not Spanish, so **not used** for the €500 per kWh |

## Test sites and city context

| Source | What it backs up |
|---|---|
| [Barcelona hands 10 municipal roofs to energy communities (Energías Renovables, 28 Sep 2026)](https://www.energias-renovables.com/autoconsumo/barcelona-impulsa-las-comunidades-energ-ticas-con-20260928/) | One roof per district, tender closed 4 Nov 2026. Lists the sites. |
| [City shared self-consumption rules (sostenible.cat, Apr 2023)](https://www.sostenible.cat/print/noticia/la-ciutadania-de-barcelona-podra-accedir-a-lautoconsum-municipal-compartit) | City pergola scheme: €70/yr per 500 W share, homes within 1 km, 30% reserved for vulnerable households. A price benchmark. |
| [BSM venues add 10,000 m² of panels (sostenible.cat, Jul 2024)](https://www.sostenible.cat/print/noticia/els-equipaments-de-bsm-incorporaran-10000-metres-quadrats-de-plaques-solars) | Port Olímpic 3,560 m² (over 825,000 kWh/yr), Anella Olímpica 2,877 m² (about 791,060 kWh/yr). |
| [Barcelona plan to triple municipal PV by 2027 (sostenible.cat, Jun 2024)](https://www.sostenible.cat/print/noticia/barcelona-aprova-mesures-per-triplicar-la-potencia-fotovoltaica-municipal-fins-al-2027) | 5,848 kWp (2023) to 19,244 kWp (2027), and 27,244 kWp by 2030. Building types targeted, including schools and markets. |
| [Illa Eficient, 22 Eixample buildings in a solar cooperative (Ara, Sep 2021)](https://es.ara.cat/sociedad/22-edificios-eixample-alian-cooperativa-energetica-fotovoltaica_1_4133725.amp.html) | A residential precedent: renovation plus PV plus batteries, first phase €3.4M, about 30% savings expected. |
| [Open Data BCN: electricity consumption](https://opendata-ajuntament.barcelona.cat/data/dataset/consum-electricitat-bcn) | Daily use per postal code, sector and 6-hour band. Area-level only, not per building. Used by `step05_forecast_demand/bcn_data.py`. |
| [Building Data Genome 2](https://github.com/buds-lab/building-data-genome-project-2) | 1,636 non-residential buildings with 2 years of hourly data. Planned training data for step 05; its accuracy on Barcelona must not be claimed. |
| [Aretian: Barcelona Metropolitan Digital Twin](https://www.aretian.com/post/aretian-unveils-the-barcelona-metropolitan-digital-twin) | Checked and **not used**: a commercial urban-analytics platform (housing, economy, mobility) with no building energy, solar or schedule data. |

## Law (kept for `--legal-mode` in step 07 and `allocation.py` in step 07; the default tool assumes direct wiring)

| Source | What it backs up |
|---|---|
| [RD 244/2019, consolidated text (BOE)](https://www.boe.es/buscar/act.php?id=BOE-A-2019-5089) | Collective self-consumption rules: 500 m (5 km for PV up to 5 MW since RDL 7/2026), shares agreed in advance, changeable every 4 months, compensation only up to 100 kW. Team legal check of 3 Nov 2026. |

## Assumptions not yet backed by a source

| Assumption | Value | Where in the code |
|---|---|---|
| Panel models: 420 W at 1.76 x 1.13 m (default) and 540 W at 2.28 x 1.13 m | typical catalogue panels; 540 W chosen because CEP9 = 58.32 kWp / 108 panels = 540 W each [CEP9 presentation] | `step02_pv_capacity/layout.py` (`MODULES`) |
| Layout options "neat blocks" and "best blocks" | rectangles of at least 12 m² / 16 m² of panels (6 / 8 panels of 420 W, 5 / 6 of 540 W), at least 2 panels wide both ways, panels at least 85% / 93% of the roof's 90th-percentile panel; chosen to look like real rooftop systems | `step03_simulate_generation/options.py` (`OPTIONS`) |
| Where the real CEP9 panels are | 4 blocks, 187 m² in all, traced by eye from the ICGC orthophoto (`ortofoto_color_vigent`, CC BY 4.0) on 15 Nov 2026: light rows on the central roofs read as panels. Not checked against an installer plan, and 187 m² is less than 108 x 2.28 x 1.13 m = 278 m² of panel, so some panels may be missing or the photo may be older than the system | `pipeline/examples/cep9_actual.json` |
| CEP9 monthly output | the reported 73,750 kWh/yr [CEP9 presentation] split over months with our step 03 shape (no monthly figures published) | `step09_publish_report/export_site_data.py` (`actual_variant`) |
| CEP9 shares in our model | school 30% [The Guardian], 30 homes x 550 kWh (middle of 400-700 [CEP9]) = 23%, the other three members split the rest equally | `website/README.md` (step 07 `agreed_shares.py --shares`) |
| System losses 14% | the value in PVGIS's own example request; **PVGIS has no default**, `loss` is a required input and its documentation gives no value [PVGIS API page, read 15 Nov 2026]. Sindhuja's repo also uses 14%. The usual range is 10-20% | `step03_simulate_generation/energy.py` (`SYSTEM_LOSSES`) |
| Power change with heat -0.35% per °C above 25 °C, panel at 420 W / 540 W | typical crystalline-silicon datasheet value; not read from a specific datasheet yet | `energy.py` (`TEMP_COEFF`) |
| Panel rows: 10° tilt, rows spaced for no shade at 25° sun height (21 Dec noon), 1.76 x 1.13 m panel | catalogue and rule-of-thumb values | `step02_pv_capacity/layout.py` |
| Orientation score: loss = 0.5 x sin(tilt) x (1 - cos(angle off south)) | a rough ranking formula for `--orient search`; the real yield comes from step 03 | `layout.py` (`yield_factor`) |
| Group search: at most 6 guests, each must add 250 kWh a year | from the matchmaker diagram's stopping rule; ASSUMPTION | `step07_share_energy/optimise.py` |
| Electricity taxes on a kWh | electricity tax 5.11% then VAT 21% (rates have changed over time) | `step07_share_energy/agreed_shares.py` (`TAX_FACTOR`) |
| LFP installed price | €195 per kWh (one shop price, see above) | `step06_prices_and_battery/battery_types.py` (`LFP_CAPEX_EUR_PER_KWH`) |
| Battery power | half its size per hour (a 2-hour battery) | `battery_types.py` (`c_rate`) |
| Export paid at the wholesale (OMIE) price | | `step06_prices_and_battery/prices.py` |
| PVPC used for big buildings too (they really pay 3.0TD) | | `prices.py` |
| Guest price = PVPC minus 10% | team choice, slider on the report page | `step07_share_energy/battery_agent.py` (`GUEST_DISCOUNT`) |
| Neighbours within 100 m, wired directly | team choice | `step07_share_energy/candidates.py` |
| Share of flats that join | 40% | `candidates.py` (`JOIN_RATE`) |
| Panel cost €1,061 per kWp central (best €730, worst €1,400) | Central: [Marblanc Solar](https://marblancsolar.com/itemised-costs-solar-panels-in-spain/), average of 10 quotes June to August 2025 for homes under 20 kW without battery (€1,061 per kW; panels about €0.15 per W, 16% of the total), page updated 11 Nov 2026. An installer's blog, so probably high for a big roof. Best: about €730 per kWp for 180 kW industrial without VAT [APPA 2024]. Worst: €1,400 is an ASSUMPTION | `investment.py` (`CASES`) |
| Upkeep €15 per kWp a year | close to NREL's "about $19/kWDC-yr for 2023" for US commercial PV [NREL ATB 2024 PV]; no Spanish figure found | `investment.py` (`OM_EUR_PER_KWP_YEAR`) |
| Flat prices for the legal-share comparison (grid 0.16, sale 0.10 ASSUMPTIONS; export 0.06 €/kWh = Endesa Solar Plus surplus price excl. taxes, see above) | | `investment.py` (`CASES`) |
| Office 120 kWh/m²/yr, school 60 kWh/m²/yr and their day shapes | to replace with trained or metered data | `step05_forecast_demand/baseline_profiles.py` |

## Demand datasets (looked at 15 Nov 2026 for `step05_forecast_demand/train_profile_model.py`)

| Source | What it backs up |
|---|---|
| [GoiEner smart meter data, Zenodo](https://zenodo.org/records/7362094) and [Scientific Data paper](https://www.nature.com/articles/s41597-023-02846-0) | 25,559 Spanish supply points, hourly kWh Nov 2014 to Jun 2022, CNAE code and contracted power in metadata.csv, 72.5% Basque Country; licence CC BY 4.0 per the paper (the Zenodo text says CC BY-SA). Training data for the demand model. Column names not yet checked on the files |
| [Open Data BCN: electricity by postal code, economic sector and time slot](https://opendata-ajuntament.barcelona.cat/data/dataset/consum-electricitat-bcn) | Datadis-based Barcelona consumption (MWh) per day, postal code, sector and time slot, CC BY 4.0. Real Barcelona day shapes by sector |
| [Madrid open data: municipal building energy, monthly](https://datos.madrid.es/dataset/?tags=kwh) and [its structure PDF (May 2024)](https://datos.madrid.es/FWProjects/egob/Catalogo/Energia/ficheros/Estructura_DS_Consumo_energ%C3%ADa_edificios_municipales.pdf) | Monthly kWh per municipal building and sensor since 2020, with building type and coordinates. Not hourly |
| [Building Data Genome 2, Zenodo](https://zenodo.org/records/3887306) | 1,636 non-residential buildings, 2 years hourly, 19 sites in North America and Europe, CC BY 4.0. No Spanish site confirmed |
| `examples/demand_model/` (our own training run on GoiEner, 15 Nov 2026) | Time-of-day shares and daily averages by building type from 2,960 real Spanish supply points (168 education, 252 office, 320 retail, 504 household). Mostly Basque Country and Navarre, mostly small businesses. Backs the 'learned' shapes in `baseline_profiles.learned_shapes()` |
