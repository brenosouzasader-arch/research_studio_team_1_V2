# Step 05: Demand for buildings without meters

**Question this step answers:** most buildings near a roof have no meter data we can see. How much power does each one use, hour by hour?

Today the answer is a **rule-based estimate**, not an AI model. It is what the guests' use in steps 07-08 is made of, so it matters a lot.

| File | What it does | Type |
|---|---|---|
| `baseline_profiles.py` | Yearly kWh from Catastro (dwellings, floor area, use) times a typical kWh per home or per m², spread over 8,760 hours with a day shape for homes, shops, offices and schools. Every number is marked ASSUMPTION | Formula (rules) |
| `bcn_data.py` | Reads real time-band, weekend and month patterns from Open Data BCN (postal code × sector × 6-hour band) and reshapes the baseline to follow them | Statistics from real data |

```
python -m step05_forecast_demand.bcn_data --site poblenou_quatre_cantons
```

| `train_profile_model.py` | **New (not yet run on real data).** Learns from real Spanish meters, by building type: (1) average kWh per day by month and weekday/weekend, (2) share of the day's use in each hour by season and weekday/weekend, (3) a gradient-boosting model of daily kWh (type, contracted power, month, weekday) tested on customers it never saw, against the plain averages | **Machine learning** + statistics |

```
python -m step05_forecast_demand.train_profile_model --metadata data\goiener\metadata.csv --series-dir data\goiener\imp-in --out data\models\demand_profile --max-series 3000
```

It needs the GoiEner data (download steps are in the script's header). The script passed its offline tests on made-up meters, but the real column names were not checked, so the first run may stop with a message telling you which name to fix.

### Datasets we looked at (read 15 Nov 2026)

| Dataset | What it holds | Fit |
|---|---|---|
| **GoiEner** [Zenodo 10.5281/zenodo.7362094; Scientific Data 2024] | Hourly kWh of 25,559 Spanish supply points, Nov 2014 to Jun 2022, with a CNAE activity code and contracted power each. Households dominate; public administration, transport, retail, hospitality have 300+ series each; some offices and industry. Basque Country 72.5%, Navarre 13.8%, Madrid 4.4%. CC BY 4.0 per the paper (the record text says CC BY-SA) | **Best open choice, used by the script.** Not Barcelona, and few offices or schools |
| **Open Data BCN, electricity by postal code, sector and time slot** [opendata-ajuntament.barcelona.cat/data/dataset/consum-electricitat-bcn] | Datadis data for the city, per day, postal code, economic sector and time slot (MWh), CC BY 4.0, updated monthly | Real Barcelona day shape by sector; already used in `bcn_data.py`. Aggregates, so no per-building model |
| **Madrid municipal buildings, monthly** [datos.madrid.es, 'Consumo de energía en edificios municipales. Datos mensuales'] | Monthly kWh (and gas) per building and sensor since 2020; types: administrative, cultural, sports, schools, social, health, safety; with coordinates | Yearly totals and seasons for schools, offices and fire stations; **monthly only, no hours**. Licence and file format not read. Not yet used |
| **Building Data Genome 2** [Zenodo 3887306; CC BY 4.0] | Hourly 2016-2017, 3,053 meters in 1,636 non-residential buildings on 19 sites in North America and Europe | Many building types, hourly, but we could not confirm any site in Spain. Not yet used |

Madrid was asked for by name. Its data is monthly, so it helps the daily and seasonal averages for schools and offices but not the time of day. For time of day we need GoiEner or the Barcelona time-slot data.

## What this step is good and bad at

- Good: the day shape (offices busy in office hours, homes in the evening) is right in kind.
- Bad: the yearly total of a building can be off by a factor of two. For CEP9 the first estimate for Can Felipa was 1.17 GWh a year; the measured 2018 average of Barcelona's civic centres is 85,100 kWh [Consums Energètics Edificis 2008-2018]. That is why the CEP9 case now takes yearly totals from the measured averages and only the day shape from here.

## How to improve it

1. **Yearly totals from measured averages by building type** (done for CEP9: institut 108,700, school 81,700, civic centre 85,100, fire station 172,800 kWh [Consums Energètics Edificis 2008-2018]). Do the same for shops, offices and hotels if the city publishes them.
2. **Day shapes from real hourly data.** The GoiEner dataset has hourly use of 25,559 Spanish supply points, some of them offices, shops and public buildings [GoiEner, Scientific Data 2024]. Averaging them by activity gives real Spanish day, week and season shapes to replace our invented ones. Building Data Genome 2 (1,636 non-residential buildings) can do the same for schools and offices, with the caution that it is not Spanish.
3. **A trained model** (gradient boosting on hour, weekday, month, temperature, use, floor area) only once we have real meter data from Barcelona. Test it on held-out buildings and report the error against the baseline. Do not claim accuracy on Barcelona buildings from other cities' data.
4. **Ask for meters** of the actual guests (Datadis with their consent; CEP9 members through the energy community).

The questions for the team are in the pipeline README ("Open questions").
