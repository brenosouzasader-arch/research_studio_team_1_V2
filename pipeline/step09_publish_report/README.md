# Step 09: Publish report

**Roadmap:** input = all previous results, sources, assumptions, validation → output = 3D host/community view + exportable feasibility report.

Not built yet (roadmap Week 3-4). Plan:

- Reuse V1's 3D map (`website/` in the V1 repository: ArcGIS, the city's 3D model, roof files per building). It was built for the Eixample co-investment communities, so it needs a new view: one host, its shortlist, and the three scenarios side by side.
- A report page that reads `host_summary.json`, `shortlist.csv`, `allocation_summary.json` and `investment_summary.json`, and marks every number as measured, modelled or assumed.

V1's map code was left out of this repository on purpose, so the pipeline stays small. Copy it in when this step starts.
