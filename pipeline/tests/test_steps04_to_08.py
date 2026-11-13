"""Offline tests for the V2 steps 04-08, with the Bruc 59 example roof as the solar input."""
import json
from pathlib import Path

import numpy as np
import pytest

from step04_read_host_demand import host_table
from step06_discover_neighbours import candidates as nb
from step07_optimize_allocation import allocation as al
from step08_compare_investment import investment as inv

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "bruc59_hourly.csv"


@pytest.fixture
def host(tmp_path):
    host_table.run(EXAMPLE, tmp_path / "host", host_kind="office", host_floor_m2=300, building_id="demo")
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
