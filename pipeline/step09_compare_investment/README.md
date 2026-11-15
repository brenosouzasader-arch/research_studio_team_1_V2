# Step 09: Compare investment

**Question this step answers:** after paying for the panels (and the battery), what does the owner earn each year, and how long until it pays back?

**Roadmap:** input = installed costs, O&M, tariffs, compensation → output = incremental benefit, self-consumption ratio, payback and sensitivities.

Our business model (team decision, 12 Nov 2026): **the owner pays for and keeps the panels and the battery, uses what it can, and sells the rest to the guests** below the grid price.

```
python -m step09_compare_investment.investment --sharing-dir data\sharing\demo --kwp 15.5 --out data\investment\demo
python -m step09_compare_investment.investment --allocation-dir data\allocation\demo --kwp 15.5 --out data\investment\demo
```

`--kwp` is the installed power from step 03 (`<name>_yield.json`). You can give both folders at once.

## With `--sharing-dir` (step 08's battery agent, real prices): `investment_battery.json`

For each price year (typical, 2023, 2024, 2025), with and without the battery, and with a central, low and high panel cost:

- capex (panels + battery), the owner's host savings, sales to guests, export income, upkeep
- **annual net value** and **simple payback**
- **net after battery wear**: also takes off the battery's cost spread over its life, because it must be replaced (LFP: after 15 years, or sooner if it cycles a lot)
- a flag if the battery wears out before the investment pays back
- what the guests save, and the guest discount used

Panel cost and upkeep are **ASSUMPTIONS** (`CASES` at the top of `investment.py`: €1,200 / 1,400 / 1,600 per kWp and €15 per kWp a year). The battery's cost comes from `step06_prices_and_battery/battery_types.py`.

## With `--allocation-dir` (step 08's sharing-law scenarios): `investment_summary.json`

The host-only, fixed and hourly scenarios at flat assumed prices (grid €0.16, sale €0.10, export €0.05 per kWh, with low and high cases). This was kept so the Spanish legal options can still be compared.

## Too many panels? Go back to step 03

The tool starts by filling the roof (team decision). If the money looks better with fewer panels, run step 03 again with `--max-panels N` (keeps the N panels that produce most) and then run steps 04 to 09 again:

```
python -m step03_simulate_generation.shade_yield "<address>" --laz-dir data\lidar --max-panels 30 --out data\pv\host_30
```

## The guest-price slider (for the report page)

Guests pay (1 − discount) × the grid price of each hour. The default discount is 10%. The report page can change it without re-running anything: `owner_total_at_discount(result, discount)` recomputes the owner's money, and each guest saves discount × `roof_kwh_at_grid_price_eur`. (The battery's choices hardly depend on the discount, because it always prefers serving the host first, then the guests, then export.)
