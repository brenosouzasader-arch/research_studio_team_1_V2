# Step 04: Read host demand

**Question this step answers:** how much does the host use each hour, and how much solar is left over?

`host_table.py` reads step 03's hourly solar output and the host's demand, and lines them up hour by hour into one 8,760-hour table.

## Is the demand verified, an estimate or a prediction?

It depends on which command you run, and every row of the output says which (`source_type`, `quality_flag`):

| Case | `source_type` / `quality_flag` | What it is |
|---|---|---|
| Meter export (`--metered`) | `metered` / `ok` | **Measured.** Real use of the building. Gaps are filled with the average of the same weekday hour (those hours are an estimate) |
| No meter (`--host-kind`, `--host-floor-m2`) | `proxy_office`, `proxy_school`... / `assumed` | **An estimate, not a prediction and not verified.** Yearly kWh = floor area × a kWh per m² for the building type, spread over the year with a typical day shape. All numbers are ASSUMPTIONS (step 05) |
| Later: a trained model (step 05) | `predicted` | **A prediction** from a model trained on other buildings. Not built yet |

Until we have meter data the whole tool rests on the estimate, so every result on the website says so. **The CEP9 case uses an estimate:** the 2018 average of Barcelona's municipal institutes (108,700 kWh a year) [Consums Energètics Edificis 2008-2018], not the school's own meter.

## Better data for the host (open question for the team)

| Option | What it gives | Catch |
|---|---|---|
| The host's own meter data (Datadis, or the utility's export; UPC SIRENA for UPC buildings) | The real thing | Needs the owner's consent; CEP9's school has not shared it with us |
| GoiEner smart-meter dataset [GoiEner, Scientific Data 2024] | Hourly use of 25,559 Spanish supply points, 2014-2022, CC BY 4.0, including offices, public buildings and shops (about 19% non-homes); 4.4% are in Madrid | Mostly the Basque Country; supply points are labelled by tariff and activity code, not by floor area; not Barcelona |
| Building Data Genome 2 | 1,636 non-residential buildings, 2 years hourly, with floor area and use type | US and Europe, no Spain; a model trained on it failed against the plain baseline in Sindhuja's repo |
| Open Data BCN electricity by postal code | Daily use per area, sector and 6-hour band | Area level, not per building; already used in step 05 for day shapes |
| A Madrid dataset | We did not find one with hourly use by building type. If you have a link, send it | Unknown |

## Run

```
# with a meter export (best): any interval, a time column and a kWh column, UTC
python -m step04_read_host_demand.host_table --solar data\pv\cep9_hourly.csv --metered data\meters\cep9.csv --building-id cep9 --out data\host\cep9

# without one: step 05's proxy profile from use type and floor area (what the website uses today)
python -m step04_read_host_demand.host_table --solar data\pv\cep9_hourly.csv --host-kind school --host-floor-m2 1811.7 --building-id cep9 --out data\host\cep9
```

Outputs in `--out`: `pv_hourly.csv`, `demand_hourly.csv`, `host_table.csv` (generation, host demand, self-consumed, surplus), `host_summary.json`, `surplus_map.png` (365 days × 24 hours).

**Try it offline:** `examples\cep9_hourly.csv` is the CEP9 roof's solar output (neat blocks, 420 W), so the second command above also works from a fresh clone (replace `data\pv\cep9_hourly.csv` with `examples\cep9_hourly.csv`).

**A real result can be "no surplus".** If `surplus_share` in the summary is small, sharing does not pay for that host. That is a valid answer.
