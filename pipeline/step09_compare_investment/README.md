# Step 09: Compare investment

**Question this step answers:** after paying for the panels (and the battery), what does the owner earn each year, and how long until it pays back?

**Roadmap:** input = installed costs, O&M, tariffs, compensation → output = incremental benefit, self-consumption ratio, payback and sensitivities.

Our business model (team decision, 12 Nov 2026): **the owner pays for and keeps the panels and the battery, uses what it can, and sells the rest to the guests** below the grid price.

```
python -m step09_compare_investment.investment --sharing-dir data\sharing\cep9 --kwp 53.34 --out data\investment\cep9
python -m step09_compare_investment.investment --allocation-dir data\allocation\cep9 --kwp 53.34 --out data\investment\cep9
```

`--kwp` is the installed power from step 03 (`<name>_yield.json`). You can give both folders at once.

## With `--sharing-dir` (step 08's battery agent, real prices): `investment_battery.json`

For each price year (typical, 2023, 2024, 2025), with and without the battery, and with a central, low and high panel cost:

- capex (panels + battery), the owner's host savings, sales to guests, export income, upkeep
- **annual net value** and **simple payback**
- **net after battery wear**: also takes off the battery's cost spread over its life, because it must be replaced (LFP: after 15 years, or sooner if it cycles a lot)
- a flag if the battery wears out before the investment pays back
- what the guests save, and the guest discount used

Panel cost and upkeep are **ASSUMPTIONS** (checked 15 Nov 2026, see below) (`CASES` at the top of `investment.py`: €1,200 / 1,400 / 1,600 per kWp and €15 per kWp a year). The battery's cost comes from `step06_prices_and_battery/battery_types.py`.

## With `--allocation-dir` (step 08's sharing-law scenarios): `investment_summary.json`

The host-only, fixed and hourly scenarios at flat assumed prices (grid €0.16, sale €0.10, export €0.05 per kWh, with low and high cases). This was kept so the Spanish legal options can still be compared.

## Too many panels? Go back to step 03

The tool starts by filling the roof (team decision). If the money looks better with fewer panels, run step 03 again with `--max-panels N` (keeps the N panels that produce most) and then run steps 04 to 09 again:

```
python -m step03_simulate_generation.shade_yield "<address>" --laz-dir data\lidar --max-panels 30 --out data\pv\host_30
```

## The guest-price slider (for the report page)

Guests pay (1 − discount) × the grid price of each hour. The default discount is 10%. The report page can change it without re-running anything: `owner_total_at_discount(result, discount)` recomputes the owner's money, and each guest saves discount × `roof_kwh_at_grid_price_eur`. (The battery's choices hardly depend on the discount, because it always prefers serving the host first, then the guests, then export.)

## Where every number comes from (checked 15 Nov 2026)

| Number | Value | Source / status |
|---|---|---|
| Panel cost per kWp | €1,200 / 1,400 / 1,600 (central 1,400) | **ASSUMPTION, probably too high for a big roof.** The only Spanish figure found is about €730 per kWp for a typical 180 kW industrial installation, without VAT (€131,400) [APPA 2024, p. 13]. US commercial PV is about US$1,780 per kWp [NREL ATB 2024 commercial PV]. Smaller roofs cost more per kWp. Not changed yet: it moves the payback a lot (see open questions) |
| Upkeep | €15 per kWp a year | **ASSUMPTION**, close to NREL's about US$19 per kWp a year [NREL ATB 2024 commercial PV]; no Spanish figure |
| Battery cost, life, efficiency | see step 06 | LFP price is an ASSUMPTION; the rest from NREL ATB 2024 and PNNL 2022 |
| Prices (PVPC, wholesale) | hourly 2023-2025 | **Measured**, REE REData |
| Guest discount | 10% | team choice, slider on the page |
| Export price | wholesale (OMIE) price of the hour | ASSUMPTION: export is paid roughly the market price |
| Flat prices for the legal comparison | grid €0.16, sale €0.10, export €0.05 per kWh | **ASSUMPTIONS**, used only with `--allocation-dir` |
| Building use | estimate | see step 04 and 05: the 2018 averages of Barcelona municipal building types, not meters |

Payback is "simple payback" (capex ÷ yearly net value, no discounting, no price changes, no panel degradation, no IBI/ICIO tax cuts), so treat it as a rough size, not a forecast.
