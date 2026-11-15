# Step 10: Publish report

**Question this step answers:** how do we show the results so anyone can check them?

`export_site_data.py` collects the outputs of steps 03 to 09 and `docs/SOURCES.md` into one file, `website/data/site_data.json`, which the website in [`../../website/`](../../website/) reads. Every headline number in it carries a label: *measured* (real prices or meters), *modelled* (computed by the pipeline) or *assumption* (a value we chose), and where it comes from.

```
python -m step10_publish_report.export_site_data --name demo --yield examples\bruc59_yield.json --lat 41.3935 --lon 2.1689
```

It needs these folders from the earlier steps: `data\host\<name>` (04), `data\prices` (06), `data\battery\<name>` (06), `data\neighbours\<name>` (07), `data\sharing\<name>` (08), `data\investment\<name>` (09).

What the website shows: the roof and its monthly solar, spare solar for every hour of the year, the buildings within 100 m and their daily use, real hourly prices and the forecast test, the battery sizes and types with an example day run by the battery agent, and the owner's money with a **guest-discount slider** (default 10%, team decision 15 Nov 2026). How to view and publish it: [`website/README.md`](../../website/README.md).

Still to add: a 3D view (V1's ArcGIS map is in the V1 repository) and the real A160 case.
