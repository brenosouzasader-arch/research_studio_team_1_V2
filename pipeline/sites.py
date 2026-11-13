"""Test-site settings. One JSON file per candidate site in ../sites/.

The code never assumes a site: every step that needs a place reads it from here
(or from its own --lat/--lon/--postal options). To switch test site, pass a
different --site name. To add a site, copy one of the JSON files in ../sites/.

    from sites import load_site
    site = load_site("upc_campus_nord")
    site["center"]["lat"], site["postal_codes"], site["hosts"]
"""
import json
from pathlib import Path

SITES_DIR = Path(__file__).resolve().parent.parent / "sites"


def site_names():
    return sorted(p.stem for p in SITES_DIR.glob("*.json"))


def load_site(name):
    path = Path(name) if str(name).endswith(".json") else SITES_DIR / f"{name}.json"
    if not path.exists():
        raise SystemExit(f"No site called {name!r}. Sites: {', '.join(site_names())}")
    site = json.loads(path.read_text(encoding="utf-8"))
    for key in ("name", "center", "postal_codes", "hosts"):
        if key not in site:
            raise SystemExit(f"{path} is missing {key!r}")
    return site
