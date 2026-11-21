# Step 01: Select host

**Roadmap:** input = address / parcel ID, building use, roof / ownership information → output = resolved footprint, coordinates, roof ID, cadastral attributes.

Carried over from V1's step 1, with a fix: LiDAR sheets that have no building class (like ICGC sheet 433584) now count their class-1 points as building. `parcels.py` is new here: every cadastral plot around a point (moved out of V1's Eixample roof list so step 07 can use it anywhere).


The first step of the rooftop solar pipeline. The input is an address, or a point tapped on a map. The output is one record per building:

| Field | From |
|---|---|
| `lat`, `lon` | ICGC geocoder, falling back to Nominatim (OpenStreetMap) |
| `refcat`: 14-character plot reference | Catastro, "Consulta_RCCOOR" service |
| `year_built`, `current_use`, `dwellings`, footprint | Catastro INSPIRE Buildings |
| `footprint_source` | `catastro`, or `lidar` when Catastro has no building on the plot (see below) |
| `floors_above_ground`: highest building part | Catastro INSPIRE Building Parts |
| `lidar_tiles`, `roof`, `flat_roof` | Your downloaded ICGC or CNIG LiDAR tiles |
| `heritage_protected` | A protected-buildings GeoJSON, if you have one (otherwise `null` = unknown) |

### Where the footprint comes from: Catastro first, LiDAR if Catastro has nothing

1. **Catastro first.** The footprint is the building that Catastro's INSPIRE Buildings service lists on the plot.
2. **LiDAR when Catastro has no building.** Some plots have a cadastral reference but no building in that service. On 21 Nov 2026 this was true of three public buildings: Institut Maria Espinalt, the Llevant fire station and Institut ITAEB. For those, `find_building` takes the plot outline (`parcels.py`) and traces the building from LiDAR (`lidar.footprint_from_lidar`): building points more than 6 m above the plot's ground (ASSUMPTION; this drops walls, canopies and low sheds), on a 1 m grid with small gaps closed. Year, use and homes then stay `null`. If the LiDAR sheets cover less than all of the plot, it warns that the outline may be cut off.
3. **Checked again in step 02.** Step 02 reads **every** building, host and participants, from both LiDAR and the ICGC orthophoto. Comparing those two with the step 01 footprint confirms that the Catastro footprint is right, or shows where it is not.

All geometry is in **EPSG:25831** (ETRS89 / UTM 31N, metres), the same system as the ICGC data. Each run writes `building.json` and `building.geojson`. Drag the `.geojson` file into QGIS to check the footprint against the orthophoto.

## Setup

See [the pipeline README](../README.md#setup-once).

## Run

Run these from the `pipeline` folder:

```bash
# 1. Check the live services work (no LiDAR needed)
python smoke_test.py

# 2. One building from an address
python -m step01_select_host.find_building "Carrer de Girona 81, Barcelona"

# 3. With LiDAR, which adds the flat-roof check
python -m step01_select_host.find_building "Carrer de Girona 81, Barcelona" --laz-dir data/lidar

# 4. From a map tap instead of an address
python -m step01_select_host.find_building --lat 41.3935 --lon 2.1689 --laz-dir data/lidar

# Offline tests (no internet needed)
python -m pytest tests
```

### Getting LiDAR tiles

Download the tiles that cover your test buildings from the **ICGC Territorial LiDAR** download viewer (3rd coverage, 2021–2023, LAZ), or from the CNIG PNOA LiDAR viewer. Put them all in one folder, such as `data/lidar/`. The code reads each file's bounds, so the file names don't matter.

## Test cases: CEP9 (primary) and A160 (secondary)

`cases/cep9.json` and `cases/a160.json` list, for each case: the host roof(s), every participant (address, Catastro address, cadastral reference, use, distance from the host), the data we have, and what is still unknown, with the next action for each. References and points were checked live on 21 Nov 2026 (ICGC geocoder + Catastro).

```bash
python -m step01_select_host.cases          # both cases
python -m step01_select_host.cases cep9     # one case
python -m step01_select_host.cases --map    # rebuild the map footprints
python -m step01_select_host.cases --site   # copy the cases into the website data
```

Main findings: CEP9's power comes from two roofs, Escola Pere IV (red, 3241427DF3834A) and Institut Quatre Cantons (yellow, 3241428DF3834A). The Institut's own address geocodes onto the red plot, so run the yellow roof from its point. Maria Espinalt, the Llevant fire station and ITAEB have a plot but no building in Catastro, so their footprints are traced from LiDAR at points Breno checked on the map. The fire station's plot runs onto LiDAR sheet 432584, which we don't have yet, so its outline is cut off. Only Can Felipa is within the 100 m default, and all A160 guests are 105-243 m away.

For the website's step 01 map: `--map` rebuilds `cases/<case>_map.geojson` (needs internet, plus the LiDAR traces in `data/host/`), and `--site` copies the cases into `website/data/site_data.json` without rerunning the other steps.

## How the flat-roof check works

1. Take the LiDAR points classed as **building** (class 6) inside the Catastro footprint.
2. Make a 0.5 m height grid from them, keeping the highest point per cell.
3. Measure the slope of each cell. Cells under 5° count as flat.
4. The roof counts as flat if at least **30%** of the cells are flat (ASSUMPTION; it was 70% until 15 Nov 2026, relaxed on the team's decision so that A160 at 33% passes). Stair housings and tanks make small steep patches, so a flat roof with obstacles still passes.

The thresholds are at the top of `lidar.py`, ready for tuning once we've seen real Barcelona roofs.

## Known gaps, and what to do about each

The same list is on the website (step 01 card), read from `known_gaps.json` in this folder.

| Gap | Where it stands | What to do next |
|---|---|---|
| Services not yet tested on many buildings | Partly resolved. Run live on 15 Nov 2026 from a laptop: the CEP9 school and the A160 office were found, geocoded and read from Catastro, ICGC and LiDAR without errors. Catastro returned no building outline for 2 CEP9 members (Institut Maria Espinalt, Llevant fire station). | Find out why those two have no outline (try their cadastral reference directly instead of the point), then run smoke_test.py on 10 more Poblenou buildings. |
| Catastro address differs from the address you typed | The CEP9 school was typed as Camí Antic de València 35 and Catastro lists it as CL BILBAO 103. Both are the same building (the plot has two street fronts). | Show both addresses in the result, and add a map tap check so the user can confirm the right building. |
| Heritage protection is unknown (flag stays empty) | The city's protected-heritage catalogue exists as open data (Open Data BCN, CC BY 4.0, 3 resources) but we have not downloaded it, so heritage_protected is null. | On a laptop: download the dataset, check which file has a cadastral reference or a polygon, and pass it with --heritage. |
| Plots with several buildings | The code picks the building containing the point, or else the largest one, and adds a warning. Not yet tested on a plot with several roofs. | Test on one such plot in Poblenou and let the user choose the building from a list. |
| Floors = highest building part | For blocks with a set-back top floor, the count includes the extension. Floors only feed the demand estimate of step 05, not the roof. | Compare Catastro floors with LiDAR height for 10 buildings and fix any that are far off. |
| Flat-roof limit was strict | A160 reads 33% flat cells. The limit was 70%, so it was flagged "not flat". Relaxed to 30% on 15 Nov 2026 (team decision). | Check on more roofs that 30% does not let steeply pitched roofs through. |

Catastro's WFS parameter really is spelled `STOREDQUERIE_ID`, in Catastro's own spelling. The live runs worked with it. If the WFS returns an error one day, check the stored-query names (`GetBuildingByParcel`, `GetBuildingPartByParcel`) in the service's GetCapabilities.

## What the website shows for this step

Each property gets a card with every field above (coordinates, cadastral reference, year, use, dwellings, floors, height, footprint, LiDAR sheets, flat-roof check, heritage, warnings), plus a search bar. The bar looks the address up among the properties we have already run (so far the CEP9 school and the A160 office; `examples/cep9_building.json` and `examples/a160_building.json`). For an address we have not run, it shows the exact command to run on a laptop, because the website has no server that can call Catastro or ICGC. Add a property to the page with `export_site_data --property <building.json>`.

## Files

```
geocode.py        address -> lat/lon (ICGC, then Nominatim)
catastro.py       lat/lon -> plot reference -> buildings and parts
lidar.py          LiDAR tiles -> roof points -> flat-roof check
height.py         building height from LiDAR
parcels.py        every plot around a point (used by step 07)
heritage.py       optional heritage layer -> flag
find_building.py  runs the steps, command line, JSON/GeoJSON output
known_gaps.json   the gaps above, read by the website
../tests/         offline tests
../smoke_test.py  live test on 4 Eixample buildings
```
