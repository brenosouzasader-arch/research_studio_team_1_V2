from sites import load_site, site_names


def test_both_candidate_sites_load():
    assert {"poblenou_quatre_cantons", "upc_campus_nord"} <= set(site_names())
    for name in site_names():
        s = load_site(name)
        assert s["hosts"] and s["postal_codes"] and "lat" in s["center"]
