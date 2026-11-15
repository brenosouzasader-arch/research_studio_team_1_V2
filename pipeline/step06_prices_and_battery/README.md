# Step 06: Prices and battery

**Question this step answers:** is a battery at the host worth it, and if so, how big?

It sits between step 05 (how much each building uses, hour by hour) and step 07 (which neighbours join), because the battery belongs to the roof owner and is first sized for the host alone. Step 07 checks the size again once the guests are known.

Every number below comes from a source in [docs/SOURCES.md](../../docs/SOURCES.md) or is marked **ASSUMPTION**.

## Why prices matter (and why Barcelona has them)

Yes, the grid price in Barcelona changes through the day:

- The Spanish wholesale market (OMIE) sets a new price every hour, and every 15 minutes since 1 October 2025. On that first day prices went from €6.67/MWh at 15:00 to €230/MWh at 21:00 [Forbes España].
- Homes and small buildings (up to 10 kW) on the regulated tariff, the **PVPC**, pay a price that follows that market hour by hour [Selectra PVPC].
- In our 2023-2025 data, the PVPC was cheapest in the afternoon (about €0.09-0.10/kWh at 14:00-16:00 local time) and dearest in the evening (about €0.20/kWh at 20:00-22:00). The evening was dearer than midday on 362-365 days a year. *(Computed by `prices.py` from the REE file; see `prices_summary.json`.)*

So a battery can store cheap midday solar and use it in the dear evening. The question is whether that earns more than the battery costs.

## The files

| File | What it does |
|---|---|
| `download_prices.py` | Run once on your laptop. Downloads the real prices for 2023-2025 from REE (PVPC and wholesale) and OMIE (wholesale, as a cross-check) into `data\prices\`. The cloud can't reach these sites. |
| `prices.py` | Reads the REE file, turns €/MWh into €/kWh, and lines every hour up with the solar year (keeping weekdays, so a Monday stays a Monday). Also says which tariff period each hour is in (2.0TD for small supplies, 3.0TD for big buildings). |
| `price_model.py` | Predicts the PVPC 2 to 7 days ahead with a machine-learning model, and checks it against two simple rules. |
| `battery_types.py` | The two batteries you can compare: LFP (default) and NMC, each with cost, efficiency and life, and a source for each number. Sodium-ion, vanadium flow and second-life car batteries were removed on 15 Nov 2026: we found no checkable numbers for them at building size. |
| `dispatch.py` | The battery controller. Decides every hour where the solar goes: to the host, a guest, the battery or the grid. Used here and in step 07. |
| `battery_size.py` | Tries battery sizes from 0 to 200 kWh for the host and says which one, if any, pays for itself. |

## How to run it

From the `pipeline` folder, after step 04:

```
python step06_prices_and_battery\download_prices.py          (once; a few minutes)
python -m step06_prices_and_battery.prices
python -m step06_prices_and_battery.price_model
python -m step06_prices_and_battery.battery_size --host-dir data\host\cep9 --out data\battery\cep9
python -m step06_prices_and_battery.battery_size --host-dir data\host\cep9 --out data\battery\cep9 --compare-types
```

Options for `battery_size`: `--price-year 2023` (or 2024, 2025; default `typical` = the average of the three years), `--type nmc`, `--sizes 0 10 20 50`, `--no-export` (if the host may not send power to the grid, so the extra is turned off instead).

## Which price we use for what

| Use | Price | Why |
|---|---|---|
| A kWh the host or a guest doesn't buy from the grid | PVPC of that hour | That is what they would have paid [Selectra PVPC] |
| A kWh sold to a guest | PVPC × (1 − 10%) | Team choice (15 Nov 2026); a slider on the report page |
| A kWh exported to the grid | Wholesale (OMIE) price of that hour | **ASSUMPTION:** export is paid roughly the market price |

**Big buildings pay differently.** Supplies over 15 kW (most offices, schools and hotels) are on the 3.0TD tariff: market price plus a grid fee that depends on six periods (P1 to P6) by season and hour, plus a fee per kW of contracted power [Endesa periods]. The PVPC is not available to them. `prices.py` already labels every hour with its 3.0TD period, but we use the PVPC for everyone until we have a real big-building bill to copy. Note: the Endesa page's tables for the high and mid-high seasons contradict themselves, so we use the hour pattern of its other two seasons (peak 9-14 h and 18-22 h). This should be checked against CNMC Circular 3/2020.

**REE or OMIE?** They give the same wholesale number: OMIE sets it, REE republishes it. In our files 99.7% of hours from January 2023 to September 2025 match to the cent; the rest are clock-change days. REE's file also has the PVPC, so it is the one the tool reads.

## The price forecast (the AI part of this step)

**When it's needed.** Tomorrow's prices are known the day before: the OMIE day-ahead market closes at 12:00 CET [OMIE] and results come out at about 12:57 [Modo Energy]. So the battery always knows the next 11 to 35 hours for sure. A forecast only helps to plan further ahead.

**The model.** A gradient-boosted decision tree (scikit-learn's `HistGradientBoostingRegressor`, the same family as XGBoost and LightGBM). For each hour it looks at the clock hour, weekday, month, the latest known prices of that hour (2 to 7 days earlier, 7 and 14 days earlier), the last known day's average, and the typical price for that month, day type and hour. It was trained on 2023-2024 and tested on 2025, a year it never saw.

**Result** (mean error in €/kWh on 2025, where the average price was €0.136/kWh; from `price_model_report.json`):

| Days ahead | Model | Same hour last week | Typical year | Winner |
|---|---|---|---|---|
| 2 | 0.0203 | 0.0250 | 0.0225 | model, 10% less error than the best rule |
| 3 | 0.0213 | 0.0250 | 0.0225 | model |
| 4 | 0.0215 | 0.0250 | 0.0225 | model |
| 5 | 0.0220 | 0.0250 | 0.0225 | model |
| 6 | 0.0220 | 0.0250 | 0.0225 | model |
| 7 | 0.0234 | 0.0250 | 0.0225 | typical year |

**Does a better forecast earn money?** Step 07 runs 2025 twice with a 10 kWh battery on the CEP9 case: once with perfect knowledge of the second day's prices, once using the typical-year price. The difference was **€3 a year** (€7,625 against €7,622). Because tomorrow's prices are published in advance and the battery empties every evening, a better long-range forecast hardly changes what the battery does. The forecast is more useful for the investment question (what will prices look like in future years) than for daily control.

## How the battery controller decides

Set-up (team decision, 15 Nov 2026): the battery is at the host, owned by the roof owner, and **charges only from the panels, never from the grid**. Guests are wired directly to the host.

Goals, in this order:

1. **Waste as little solar as possible.** Waste = solar that no building uses: exported, turned off (curtailed), or lost inside the battery.
2. **Then make the owner the most money.** A kWh the host uses saves it the PVPC; a kWh sold to a guest earns 90% of the PVPC; an exported kWh earns the wholesale price.
3. **No guest ever pays more than the grid.** Guests pay 90% of the PVPC of that same hour, only for what they use. The code checks every guest's bill.

How: once a day the controller plans the next 48 hours as a linear program (scipy's HiGHS solver), carries out the first 24 hours, and plans again. A linear program is a standard maths method that finds the best plan within limits: the battery's size and power, each building's use, and energy that can't come from nowhere. It is a transparent optimiser, not a trained AI. Every hour's decision is saved (step 07's `decisions_hourly.csv`) so a faster learned controller (supervised or reinforcement learning) can be trained on it later.

## How the size is chosen

For each size the controller runs the whole year. Then:

- **capex** = kWh × installed price per kWh (`battery_types.py`)
- **battery life** = the shorter of its calendar life and cycle life ÷ cycles per year
- **yearly cost** = capex ÷ life + upkeep
- **yearly gain** = the owner's money with the battery − without it
- **net per year** = yearly gain − yearly cost. Above 0, the battery pays for itself.
- **break-even price** = the installed €/kWh at which net per year would be 0, which shows how much cheaper batteries must get.

Before that there is a quick **screen** with no battery model: day by day, how much midday surplus could have covered the host's own later use. That is the most any battery could ever move.

## Result so far

No real result yet. The only run is on the CEP9 school, whose use is an estimate (the 2018 average of Barcelona's municipal institutes, not the school's meter) and whose battery price is an ASSUMPTION. The earlier run used €500/kWh, where no size paid. The price is now €195/kWh (see below), so that result is out of date: rerun step 06 `battery_size` on the laptop. **Do not use this to decide a battery size.** The decision needs the owner's real meter data and a Barcelona installer's quote.

## Battery numbers and where they come from

| Type | €/kWh installed | Round trip | Cycle life | Calendar life | Usable share |
|---|---|---|---|---|---|
| LFP (default) | 195 (shop price, one product; **ASSUMPTION** for big buildings) | 85% [NREL ATB 2024] | 2,400 [PNNL 2022] | 15 y [NREL ATB 2024] | 80% [PNNL 2022] |
| NMC | 220 (LFP × 435/385 [PNNL 2022]) | 85% [NREL ATB 2024] | 1,520 [PNNL 2022] | 13 y [PNNL 2022] | 80% [PNNL 2022] |

Both: upkeep 2.5% of capex a year [NREL ATB 2024] and charge or discharge at up to half the size per hour (a 2-hour battery, **ASSUMPTION**).

**How reliable is this data?** The performance numbers (efficiency, cycles, life) come from two US government labs' studies of grid-scale batteries [NREL ATB 2024, PNNL 2022]; they are published and checkable but describe utility-size plants, not a 50 kWh unit in a Barcelona basement. The price is the weak spot: we found **no checkable installed price for a 20-500 kWh building battery in Spain or the EU**. The one recent figure we found is a UK installer blog in pounds, £200-800 per kWh depending on size, which even contradicts itself between sizes [Reonic 2026], so we did not use it. The cost ratio between LFP and NMC comes from PNNL's 100 MW plants. Before the final report, get a quote from a Barcelona installer and change `LFP_CAPEX_EUR_PER_KWH` in `battery_types.py`. Suggested message to an installer is in the pipeline README ("Open questions").

## Tests

`tests/test_step06_prices_and_battery.py` checks that time zones and 15-minute prices are read right, that weekdays stay weekdays, the tariff periods, that the battery never charges from the grid and never goes below empty or above full, that energy is conserved, that the battery moves midday solar to the evening and wastes less, that no guest pays more than the grid, and the money formulas.
