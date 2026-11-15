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

(An AI model, `forecast.py`, is not built: we would only train it on real meter data, and we do not have any yet.)

## What this step is good and bad at

- Good: the day shape (offices busy in office hours, homes in the evening) is right in kind.
- Bad: the yearly total of a building can be off by a factor of two. For CEP9 the first estimate for Can Felipa was 1.17 GWh a year; the measured 2018 average of Barcelona's civic centres is 85,100 kWh [Consums Energètics Edificis 2008-2018]. That is why the CEP9 case now takes yearly totals from the measured averages and only the day shape from here.

## How to improve it

1. **Yearly totals from measured averages by building type** (done for CEP9: institut 108,700, school 81,700, civic centre 85,100, fire station 172,800 kWh [Consums Energètics Edificis 2008-2018]). Do the same for shops, offices and hotels if the city publishes them.
2. **Day shapes from real hourly data.** The GoiEner dataset has hourly use of 25,559 Spanish supply points, some of them offices, shops and public buildings [GoiEner, Scientific Data 2024]. Averaging them by activity gives real Spanish day, week and season shapes to replace our invented ones. Building Data Genome 2 (1,636 non-residential buildings) can do the same for schools and offices, with the caution that it is not Spanish.
3. **A trained model** (gradient boosting on hour, weekday, month, temperature, use, floor area) only once we have real meter data from Barcelona. Test it on held-out buildings and report the error against the baseline. Do not claim accuracy on Barcelona buildings from other cities' data.
4. **Ask for meters** of the actual guests (Datadis with their consent; CEP9 members through the energy community).

The questions for the team are in the pipeline README ("Open questions").
