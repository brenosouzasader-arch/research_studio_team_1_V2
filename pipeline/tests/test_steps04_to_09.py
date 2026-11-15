"""Offline tests for the V2 steps 04, 07, 08 and 09, with the CEP9 school roof (neat blocks, 420 W) as the solar input."""
import json
from pathlib import Path

import numpy as np
import pytest

from step04_read_host_demand import host_table
from step07_share_energy import candidates as nb
from step07_share_energy import allocation as al
from step08_compare_investment import investment as inv

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "cep9_hourly.csv"


@pytest.fixture
def host(tmp_path):
    host_table.run(EXAMPLE, tmp_path / "host", host_kind="school", host_floor_m2=1812, building_id="demo")
    return tmp_path / "host"


def test_host_table_has_8760_aligned_hours_and_conserves_energy(host):
    t = host_table.read_host_table(host)
    assert len(t["times"]) == 8760
    g, d, s, x = t["generation_kwh"], t["host_demand_kwh"], t["self_consumed_kwh"], t["surplus_kwh"]
    assert np.allclose(s + x, g, atol=1e-3)
    assert (s <= d + 1e-3).all() and (x >= 0).all()
    summary = json.loads((host / "host_summary.json").read_text())
    assert summary["surplus_weekend_kwh"] > 0          # an office roof gives surplus at weekends
    for f in ("pv_hourly.csv", "demand_hourly.csv", "surplus_map.png"):
        assert (host / f).exists()


def test_metered_15_minute_data_is_summed_per_hour(tmp_path):
    times, _ = host_table.read_hourly(EXAMPLE)
    rows = ["time_utc,kwh"]
    for t in times[:48]:
        base = np.datetime64(str(t)[:13] + ":00")
        for q in range(4):
            rows.append(f"{base + np.timedelta64(15 * q, 'm')},0.25")
    meter = tmp_path / "meter.csv"
    meter.write_text("\n".join(rows))
    use = host_table.read_metered(meter, times)
    assert np.allclose(use[:48], 1.0)                 # four quarters of 0.25 kWh
    assert np.isfinite(use).all()                     # gaps filled


def test_shortlist_keeps_only_buildings_within_reach(host, tmp_path):
    t = host_table.read_host_table(host)
    cands = [{"building_id": "near_flats", "lat": 41.3936, "lon": 2.1690, "use_type": "home", "floor_m2": 1700, "dwellings": 20},
             {"building_id": "near_shop", "lat": 41.3940, "lon": 2.1680, "use_type": "shop", "floor_m2": 400},
             {"building_id": "far_flats", "lat": 41.4100, "lon": 2.1900, "use_type": "home", "floor_m2": 1000, "dwellings": 12}]
    scored, best, demand = nb.shortlist(t, cands, (41.3935, 2.1689))
    assert {r["building_id"] for r in best} == {"near_flats", "near_shop"}
    assert next(r for r in scored if r["building_id"] == "far_flats")["eligible_status"] == "out of reach"
    nb.write_outputs(tmp_path / "nb", t["times"], scored, best, demand)
    assert set(nb.read_demand(tmp_path / "nb" / "demand_hourly.csv")) == {"near_flats", "near_shop"}


def _toy():
    gen = np.array([0.0, 10.0, 10.0, 4.0])
    demands = [np.array([1.0, 6.0, 12.0, 1.0]), np.array([2.0, 3.0, 3.0, 0.0]), np.array([0.0, 5.0, 1.0, 1.0])]
    return gen, demands


@pytest.mark.parametrize("name", list(al.SCENARIOS))
def test_every_scenario_keeps_the_coefficient_rules_and_conserves_energy(name):
    gen, demands = _toy()
    beta = al.SCENARIOS[name](gen, demands)
    al.check(beta, gen)                               # beta >= 0, sums to 1 where there is output
    a, u, e = al.account(beta, gen, demands)
    assert np.allclose(u.sum(0) + e.sum(0), gen)
    assert (u <= np.array(demands) + 1e-9).all()      # nobody uses more than they need


def test_hourly_serves_the_host_first_and_never_beats_perfect_use():
    gen, demands = _toy()
    res = al.run(gen, ["host", "a", "b"], demands)
    used = {k: v["used"].sum() for k, v in res.items()}
    best_possible = np.minimum(gen, np.sum(demands, 0)).sum()
    assert used["hourly"] == pytest.approx(best_possible)
    assert used["hourly"] >= used["fixed"] - 1e-9 and used["hourly"] >= used["host_only"] - 1e-9
    assert np.allclose(res["hourly"]["used"][0], np.minimum(gen, demands[0]))


def test_prediction_errors_show_up_as_lost_use():
    gen, predicted = _toy()
    actual = [d * 0.5 for d in predicted]
    res = al.run(gen, ["host", "a", "b"], predicted, actual)
    assert res["hourly"]["excess"].sum() > 0


def test_check_rejects_bad_betas():
    gen = np.array([1.0, 1.0])
    with pytest.raises(ValueError):
        al.check(np.array([[0.7, 1.2], [0.2, -0.2]]), gen)
    with pytest.raises(ValueError):
        al.check(np.array([[0.5, 0.5], [0.2, 0.2]]), gen)


def test_investment_compares_with_host_only():
    gen, demands = _toy()
    ids = ["host", "a", "b"]
    s = al.summary(al.run(gen, ids, demands), gen, ids)
    rows = inv.evaluate(s, kwp=1.0)
    central = {r["scenario"]: r for r in rows if r["case"] == "central"}
    assert central["host_only"]["incremental_vs_host_only_eur"] == 0
    assert central["hourly"]["annual_net_value_eur"] >= central["host_only"]["annual_net_value_eur"]
    assert {r["case"] for r in rows} == {"central", "low", "high"}


def test_meter_weekdays_stay_weekdays_when_moved_to_the_solar_year():
    # 2025-01-06 was a Monday; in the solar year (2023) it must land on a Monday too
    t = np.array(["2025-01-06T10:00"], dtype="datetime64[m]")
    moved, _ = host_table.align_to_year(t, np.datetime64("2023-01-01T00:00"))
    day = moved.astype("datetime64[D]")[0]
    assert str(day).startswith("2023-01") and (day.astype(int) + 3) % 7 == 0   # 0 = Monday


def test_neighbours_closest_first_within_100_m_and_legal_mode(host):
    t = host_table.read_host_table(host)
    cands = [{"building_id": "at_90m", "lat": 41.3940, "lon": 2.1680, "use_type": "shop", "floor_m2": 400},
             {"building_id": "at_15m", "lat": 41.3936, "lon": 2.1690, "use_type": "home", "floor_m2": 1700, "dwellings": 20},
             {"building_id": "at_160m", "lat": 41.3925, "lon": 2.1675, "use_type": "school", "floor_m2": 2000}]
    _, best, _ = nb.shortlist(t, cands, (41.3935, 2.1689))
    assert [r["building_id"] for r in best] == ["at_15m", "at_90m"]          # 100 m, closest first
    _, best, _ = nb.shortlist(t, cands, (41.3935, 2.1689), max_distance=nb.LEGAL_MAX_DISTANCE_M,
                              margin=nb.LEGAL_MARGIN_M, rank="fit")
    assert len(best) == 3 and best[0]["fit_kwh"] >= best[-1]["fit_kwh"]       # legal mode: 450 m, best fit first


def test_battery_investment_rows_and_guest_slider():
    from step06_prices_and_battery import battery_types as bt
    from step06_prices_and_battery import dispatch
    gen = np.tile(np.r_[np.zeros(8), np.full(8, 50.0), np.zeros(8)], 2)
    demand = np.vstack([np.full(48, 10.0), np.full(48, 5.0)])
    price, spot = np.full(48, 0.15), np.full(48, 0.05)
    res = {}
    for label, kwh in (("with_battery", 10.0), ("without_battery", 0.0)):
        b = {**bt.get("lfp"), "kwh": kwh}
        f = dispatch.simulate_year(gen, demand, price, spot, b)
        res[label] = dispatch.account(f, gen, demand, price, spot, 0.10, ["host", "g"], b)
    sharing = {"battery_type": "lfp", "battery_kwh": 10.0, "price_years": {"typical": res}}
    rows = inv.evaluate_battery(sharing, kwp=10)
    assert {r["scenario"] for r in rows} == {"direct_no_battery", "direct_with_battery"}
    w = next(r for r in rows if r["scenario"] == "direct_with_battery" and r["case"] == "central")
    assert w["capex_eur"] == 10 * 1061 + 10 * 195
    r = res["with_battery"]
    assert inv.owner_total_at_discount(r, 0.10) == pytest.approx(r["owner_total_eur"], abs=1)
    assert inv.owner_total_at_discount(r, 0.30) < inv.owner_total_at_discount(r, 0.10)


def test_agreed_shares_fixed_and_free():
    import numpy as np
    from step07_share_energy import agreed_shares as ag
    gen = np.array([0.0, 10.0, 10.0])
    demands = np.array([[0, 2, 10], [0, 10, 0], [0, 10, 10]])
    shares = ag.parse_shares("host=0.5", ["host", "a", "b"])
    assert np.allclose(shares, [0.5, 0.25, 0.25])
    res = ag.run(gen, ["host", "a", "b"], demands, shares, np.ones(3), guest_price=0.0)
    assert res["used_kwh"] + res["to_grid_kwh"] == 20
    assert res["per_building"]["host"]["used_kwh"] == 7        # 2 + 5
    assert res["per_building"]["a"]["to_grid_kwh"] == 2        # its share in hour 3 isn't needed
    assert res["per_building"]["a"]["saving_eur"] == 2         # free: saves its used kWh x price


# ---- steps 07 + 08 as one tool: the group optimiser (step07_share_energy/optimise.py) -------------
from step07_share_energy import optimise as opt


def _case(mode="wired"):
    h = np.arange(8760) % 24
    gen = np.where((h >= 8) & (h < 17), 10.0, 0.0)
    host = np.where((h >= 8) & (h < 17), 4.0, 0.5)                 # the host uses 4 of 10 kW by day
    day = np.where((h >= 8) & (h < 17), 3.0, 0.2)                  # a daytime user, 3 kW
    night = np.where(h >= 18, 3.0, 0.0)                            # uses nothing while the sun shines
    big = np.where((h >= 8) & (h < 17), 5.0, 0.0)
    price = np.full(8760, 0.15)
    return opt.Case(gen, host, ["day", "night", "big"], [day, night, big], price, price * 0.5, mode)


def test_optimiser_keeps_the_buildings_that_use_solar_and_skips_the_one_that_does_not():
    seen, exhaustive = opt.search(_case())
    assert exhaustive and len(seen) == 8                            # every group of 3 buildings: 2**3
    best = max(seen, key=lambda k: seen[k]["score"])
    assert set(best) == {0, 2}                                      # day + big; "night" adds nothing
    assert seen[best]["used_kwh"] > seen[()]["used_kwh"]


def test_wired_sharing_wastes_no_more_than_fixed_shares():
    for ids in [(0,), (0, 2), (0, 1, 2)]:
        wired, fixed = _case("wired").evaluate(ids), _case("legal").evaluate(ids)
        assert wired["used_kwh"] >= fixed["used_kwh"] - 1e-6
        for m in (wired, fixed):                                    # energy is conserved
            assert abs(m["used_kwh"] + m["export_kwh"] - 90 * 365) < 1e-3


def test_optimiser_falls_back_to_local_search_when_there_are_too_many_groups():
    seen, exhaustive = opt.search(_case(), exhaustive_limit=3, random_starts=5)
    assert not exhaustive and len(seen) >= 3
    assert set(max(seen, key=lambda k: seen[k]["score"])) == {0, 2}


def test_no_guest_pays_more_than_the_grid():
    m = _case().evaluate((0, 2))
    assert m["guests_save_eur"] >= 0
