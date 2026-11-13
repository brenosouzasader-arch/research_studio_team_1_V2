# Test sites

We have not picked the test site yet. Each candidate is one JSON file here, and the code reads whichever you name with `--site`. No step assumes a place.

| File | Site | Why |
|---|---|---|
| `poblenou_quatre_cantons.json` | Poblenou / 22@ around the Quatre Cantons school | A real community (CEP9) to check our numbers against; 22@ offices as hosts |
| `upc_campus_nord.json` | UPC Campus Diagonal Nord | 15-minute meter data (on request); existing PV only ~50% used on site |

Each file has: `name`, `center` (lat, lon), `postal_codes` (for Open Data BCN), `max_distance_m`, `hosts` (name, address, kind) and notes. Lines marked **CHECK** still need a real value.

To add a site (for example our old Eixample blocks), copy a file and change it. Background: [../docs/test-sites.md](../docs/test-sites.md).
