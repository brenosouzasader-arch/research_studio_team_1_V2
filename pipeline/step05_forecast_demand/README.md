# Step 05: Forecast demand (the AI step)

**Roadmap:** input = historical load, weekday/weekend, temperature, month, building category → output = predicted hourly load with error metrics and a confidence band.

| File | What it does | Status |
|---|---|---|
| `baseline_profiles.py` | The **rule-based baseline**: yearly kWh from Catastro (dwellings, floor area, use) spread over 8,760 hours with day shapes for home, shop, office and school. Every number is marked ASSUMPTION | From V1 step 5 (`demand.py`), unchanged |
| `bcn_data.py` | Learns real time-band, weekend and month patterns from Open Data BCN (postal code × sector × time band) and rescales the baseline | From V1, now takes `--site` |
| `forecast.py` | The trained model (gradient boosting) | **To build in Week 2**, only if we get meter data |

```
python -m step05_forecast_demand.bcn_data --site upc_campus_nord
```

## Plan for the model (roadmap Week 2)

1. Features per hour: hour, weekday, holiday, month, temperature (PVGIS/Meteocat), building use, floor area.
2. Target: metered kWh (UPC SIRENA or Datadis). Without it we do not train; we say so and keep the baseline.
3. Test on held-out weeks and, if possible, a held-out building. Report MAE, RMSE and bias against `baseline_profiles.py`.
4. Write `validation_report.json` (baseline_name, metric, value, sample_n, split_method, failures).

Building Data Genome 2 (1,636 buildings, hourly) can be used to try the model while Barcelona data is requested, but its accuracy on Barcelona buildings must not be claimed.
