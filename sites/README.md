# Test sites

Main real test case: **CEP9 school at Quatre Cantons** (picked 15 Nov 2026). Second: **A160**, with its roof assumed empty. Each candidate is one JSON file here, and the code reads whichever you name with `--site`. No step assumes a place.

| File | Site | Why |
|---|---|---|
| `poblenou_quatre_cantons.json` | Poblenou / 22@ around the Quatre Cantons school | A real community (CEP9) to check our numbers against; 22@ offices as hosts |
| `poblenou_almogavers_160.json` | Almogàvers 160 office (from Sindhuja's repo) | Big office roof; compare our steps 01-03 with her LiDAR layout |
| `upc_campus_nord.json` | UPC Campus Diagonal Nord | 15-minute meter data (on request); existing PV only ~50% used on site |

Each file has: `name`, `center` (lat, lon), `postal_codes` (for Open Data BCN), `max_distance_m` (100 m: guests are wired directly), `hosts` (name, address, kind) and notes. Lines marked **CHECK** still need a real value.

To add a site (for example our old Eixample blocks), copy a file and change it. The sources for each site are in [../docs/SOURCES.md](../docs/SOURCES.md#test-sites-and-city-context).
