# Step 08: Compare investment

**Roadmap:** input = installed costs, O&M, tariffs, compensation → output = incremental benefit, self-consumption ratio, payback and sensitivities.

`investment.py` (new in V2) puts money on each scenario from step 07, for our business model: **the owner pays for and keeps the panels, uses what it can, and sells the rest to the participants at a fixed price** below the grid price.

```
python -m step08_compare_investment.investment --allocation-dir data\allocation\demo --kwp 15.5 --out data\investment\demo
```

Output: `investment_summary.json`, with each scenario in a central, low and high case: capex, host bill savings, sales to participants, export value, O&M, net value per year, simple payback, participant savings, and the gain over host-only.

All prices are ASSUMPTIONS at the top of the file (capex 1,400 EUR/kWp, grid 0.16, sale 0.10, export 0.05 EUR/kWh). Whether the owner may charge participants this way is still being checked.

Money constants come from V1's step 5c (`communities.py`); the co-investment logic was not carried over.
