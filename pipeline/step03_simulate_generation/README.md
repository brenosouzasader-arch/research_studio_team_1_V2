# Step 03: Simulate generation

**Roadmap:** input = panel layout, LiDAR shadow horizon, PVGIS hourly weather → output = timestamped hourly PV generation G[h], annual kWh, shading losses.

Carried over from V1's steps 3 and 4. Step 3 places panel rows on the usable roof that step 02 found. Step 4 works out, hour by hour for a typical year, how much electricity each panel makes after shade from neighbours, trees and rooftop structures.

| | What it uses | What it gives |
|---|---|---|
| Layout, `../step02_pv_capacity/layout.py` | Step 2 usable area, building footprint | Panel rows: 1.76 × 1.13 m panels, 420 W, 10° tilt, facing the building side closest to south, rows spaced for no row-to-row shade at winter noon |
| Shade and yield, this folder | ICGC LiDAR within 150 m (roofs, ground, trees, rooftop structures), PVGIS typical year | kWh per panel per hour, shade loss per panel, yearly and monthly totals, kWh per kWp |

## Setup (once)

Download the sunshine data (free, no key). `--site` centres it on a test site in `../../sites`:

```
python -m step03_simulate_generation.weather --site upc_campus_nord
```

This writes `data\weather\barcelona_tmy.json` (8760 hours from PVGIS).

## One roof

```
python -m step03_simulate_generation.shade_yield "Camí Antic de València 35, Barcelona" --laz-dir data\lidar --usable cep9_usable.geojson --layout neat --out data\pv\cep9
```

`--usable` takes a step 02 reading you already have; leave it out and the roof is read from LiDAR.

Panels that lose more than 40% of their sun to shade are left out (for example on a lower terrace under the building's own top floors). Change the limit with `--max-shade 0.3`, or keep every panel with `--max-shade 1`.

Outputs (for `--out data\pv\cep9`):
- `cep9_yield.json`: panels, kWp, yearly kWh, kWh per kWp, mean shade loss, monthly kWh, every panel with its kWh and shade loss, all six layouts under `variants`, and the orientation tried
- `cep9_hourly.csv`: 8760 hours of kWh for the whole roof (input for step 04 and the sharing tool); one more file per layout, `cep9_hourly_<W>_<option>.csv`
- `cep9_panels.geojson`: panel outlines (EPSG:25831), opens in QGIS
- `cep9_panels.png` and `cep9_options.png`: the layout, and all layouts side by side
- `cep9_usable.geojson`: the usable roof it used (only when you leave out `--usable`)

## How the calculation works

1. **Sun path:** sun position for every hour of the year (`sun.py`, same formulas as the 3D map).
2. **Horizon:** a 1 m height grid from all LiDAR points within 150 m. From each panel, 36 directions are walked outwards and the steepest angle to anything taller is kept.
3. **Shade:** the sun is blocked when it is lower than the horizon in its direction. Diffuse sky light is scaled by the share of open sky.
4. **Sun on the panel:** direct + diffuse + light reflected by the roof (albedo 0.2), on the tilted panel.
5. **Electricity:** the panel's watts (420 W or 540 W), minus heat losses (−0.35% per °C above 25 °C, **ASSUMPTION**: a typical crystalline-silicon datasheet value) and 14% system losses (**ASSUMPTION**: PVGIS has no default for losses; 14 is the value in its own example request [PVGIS API page]; Sindhuja's repo uses it too; the usual range is 10-20%).

## Checks

Done: CEP9 school, 15 Nov 2026. With the real panels' spots our model gives 1,381 kWh per kWp, and on the whole roof 1,317, against 1,265 reported by CEP9 [CEP9 presentation]: 4-9% higher. Reasons not yet separated: weather year (PVGIS typical year vs the real years), the assumed 14% losses, and panels at a slightly different tilt.

To do:
- Compare yearly kWh with PVGIS's own tool for the same kWp, tilt and direction on 10 open roofs (target ±10%).
- Compare shade loss with Google Solar or Ladybug on a few shaded roofs.
- Check the temperature coefficient and system losses against a datasheet and an inverter spec.

## Known limits

- Trees are solid in winter too (LiDAR is captured with leaves on).
- Panels on a roof the LiDAR misses (new buildings since 2023) are not shaded correctly.
- No snow, no soiling seasons, no inverter clipping.

## Layout options and panel size (`--layout`, `--panel-wp`, `--orient`)

Real installers build neat blocks on the best part of a roof and leave out single panels and weaker spots. So every run works out three layouts, for both 420 W and 540 W panels (`--compare-wp 420,540`):

| Option | What it keeps |
|---|---|
| `max` Fill the roof | every panel that fits and loses at most 40% of its sun (default) |
| `neat` Neat blocks | rectangles of at least 12 m² of panels, at least 2 panels wide both ways, each panel at least 85% of the roof's best |
| `best` Best blocks | rectangles of at least 16 m² of panels, at least 2 panels wide both ways, each panel at least 93% of the roof's best |

How a layout is made, step by step (the website shows these steps and the panels dropped at each one, with the reason):

1. **Fit:** lay panel rows on the usable roof, as many as fit.
2. **Shade:** drop panels that lose more than 40% of their sun.
3. **Cut-off:** for neat and best, drop panels below 85% / 93% of "the roof's best" (the 90th-percentile panel). Reason shown: *weak*.
4. **Blocks:** from the panels left, repeatedly take the biggest rectangle that is big enough and keep it as a block. Panels that are good but are in no big enough rectangle are dropped. Reason shown: *loose*.

Changes made 15 Nov 2026 after review: a block is judged the same whichever way it runs (2 × 3 and 3 × 2 panels are the same block; a single row never counts), and its size is an area, so the bigger 540 W panel needs fewer panels (5 instead of 6 for a neat block). The areas (12 and 16 m²), the "2 wide" rule and the 85% / 93% cut-offs are ASSUMPTIONS (see `options.py` and docs/SOURCES.md): they are meant to be adjusted once we see more real systems.

The run prints a table of all six layouts and draws them in `<out>_options.png`. All layouts are listed under `variants` in `<out>_yield.json`, each with its `funnel` (how many panels at each step) and `left_out` (which panels and why). `--layout neat --panel-wp 540` makes that layout the main output (`<out>_hourly.csv`), which steps 04-09 use.

First test, CEP9 school (15 Nov 2026): the real system is 108 panels of 540 W in tidy rows; our "fill the roof" placed 197 of 420 W, including about 85 scattered on the cluttered south roof. **The numbers on the website for neat and best blocks were made with the old rule (6+ panels, 3+ per row); rerun step 03 and step 09 to refresh them.**

## Fewer panels (`--max-panels`)

By default every panel that fits is placed (team decision, 15 Nov 2026: fill the roof). After seeing the money in step 08, you can try a smaller system: `--max-panels 30` keeps the 30 panels that produce most and writes a new hourly file. Then run steps 04 to 09 again with it.

## Panel size and several roofs (added 15 Nov 2026)

- **Your own panel size:** `--panel-wp 540 --panel-size 2.38x1.13` replaces the catalogue size of that wattage for the run (length x width in metres). `--portrait` puts the long side up the slope. The two built-in sizes (420 W, 1.76 x 1.13 m and 540 W, 2.28 x 1.13 m) are ASSUMPTIONS from typical catalogue panels. Use the datasheet of the panel really installed when you know it. The layout block rules count an area, so a bigger panel needs fewer cells per block.
- **A host with panels on more than one building** (CEP9 is the Escola Pere IV and the Institut Quatre Cantons): run this step once per roof, then `python -m step03_simulate_generation.combine_roofs --roof red=data\pv\cep9_red_yield.json --roof yellow=data\pv\cep9_yellow_yield.json --out data\pv\cep9`. It adds panels, kWp and hourly solar for every layout and keeps a `roof` label on each panel.

