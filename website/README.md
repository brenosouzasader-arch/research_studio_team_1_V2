# Website

The results page for the tool: one page, one section per question, every number tagged *measured*, *modelled* or *assumption* with its source.

- `index.html`, `styles.css`, `app.js`: the page. Plain HTML, CSS and JavaScript, no build step. Charts are drawn as SVG by `app.js`.
- `data/site_data.json`: everything the page shows. **Don't edit it by hand.** It is written by the pipeline.

## Update the numbers

After running steps 03 to 09 for a case (see `pipeline/README.md`), from the `pipeline` folder:

```
python -m step10_publish_report.export_site_data --name demo --yield examples\bruc59_yield.json --lat 41.3935 --lon 2.1689
```

`--name` is the folder name you used in `data\host\<name>`, `data\sharing\<name>` and so on. `--lat --lon` are the host's position (the same as in step 07). Then commit `website/data/site_data.json` and push.

## See it on your laptop

```
cd website
python -m http.server 8000
```

Open http://localhost:8000. (Opening `index.html` by double-click doesn't work, because the browser won't load the data file that way.)

## Online

`.github/workflows/pages.yml` publishes this folder on GitHub Pages each time `main` changes. It needs one switch, once: on GitHub, **Settings → Pages → Build and deployment → Source: GitHub Actions**. The address is then https://brenosouzasader-arch.github.io/research_studio_team_1_V2/.

## What the page does itself

Only the guest-discount slider does any maths, using the same formula as step 09 (`owner_total_at_discount`): owner = host savings + (1 − discount) × guests' solar at grid price + export. Everything else is read from the data file.
