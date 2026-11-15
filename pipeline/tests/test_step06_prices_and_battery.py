"""Offline tests for step 06 (prices, tariff periods, battery types, the battery controller)."""
import numpy as np
import pytest

from step06_prices_and_battery import battery_types as bt
from step06_prices_and_battery import dispatch
from step06_prices_and_battery import prices as pr
from step06_prices_and_battery.battery_size import money, screen


def test_read_prices_converts_to_utc_eur_per_kwh_and_averages_quarters(tmp_path):
    f = tmp_path / "p.csv"
    f.write_text("datetime,series,eur_mwh\n"
                 "2023-01-01T00:00:00.000+01:00,PVPC,100\n"            # winter: UTC+1
                 "2023-07-01T00:00:00.000+02:00,PVPC,200\n"            # summer: UTC+2
                 "2025-11-01T10:00:00.000+01:00,Precio mercado spot,40\n"
                 "2025-11-01T10:15:00.000+01:00,Precio mercado spot,60\n"
                 "2025-11-01T10:30:00.000+01:00,Precio mercado spot,80\n"
                 "2025-11-01T10:45:00.000+01:00,Precio mercado spot,100\n")
    p = pr.read_prices(f)
    assert p["PVPC"][np.datetime64("2022-12-31T23", "h")] == pytest.approx(0.100)
    assert p["PVPC"][np.datetime64("2023-06-30T22", "h")] == pytest.approx(0.200)
    assert p["Precio mercado spot"][np.datetime64("2025-11-01T09", "h")] == pytest.approx(0.070)


def test_prices_move_to_the_solar_year_keeping_weekdays():
    # one price per hour of 2024, equal to the weekday number (0 = Monday)
    hours = np.arange(np.datetime64("2024-01-01T00", "h"), np.datetime64("2025-01-01T00", "h"))
    weekday = ((hours.astype("datetime64[D]").astype(int) + 3) % 7).astype(float)
    series = dict(zip(hours, weekday))
    solar = np.arange(np.datetime64("2023-01-01T00:30"), np.datetime64("2023-12-31T23:31"), np.timedelta64(1, "h"))
    moved = pr.to_solar_year(series, solar, 2024)
    solar_weekday = (solar.astype("datetime64[D]").astype(int) + 3) % 7
    assert np.array_equal(moved, solar_weekday)


@pytest.mark.parametrize("hour,weekday,expected", [(10, 0, "P1"), (19, 2, "P1"), (9, 4, "P2"), (15, 1, "P2"),
                                                   (3, 0, "P3"), (12, 5, "P3")])
def test_2_0td_periods(hour, weekday, expected):
    assert pr.period_2_0td(hour, weekday) == expected


@pytest.mark.parametrize("hour,weekday,month,expected", [(10, 0, 1, "P1"), (15, 0, 1, "P2"), (19, 0, 3, "P2"),
                                                         (8, 0, 6, "P4"), (12, 0, 4, "P4"), (23, 0, 10, "P5"),
                                                         (7, 0, 1, "P6"), (12, 6, 7, "P6")])
def test_3_0td_periods(hour, weekday, month, expected):
    assert pr.period_3_0td(hour, weekday, month) == expected


def test_battery_types_have_every_field_and_sensible_values():
    for name in bt.TYPES:
        b = bt.get(name)
        assert 0 < b["round_trip"] <= 1 and 0 < b["usable_share"] <= 1 and b["capex_eur_per_kwh"] > 0
        assert b["notes"]
    lfp = bt.get("lfp")
    assert bt.life_years(lfp, 100) == lfp["calendar_years"]               # little use: age decides
    assert bt.life_years(lfp, 400) == pytest.approx(lfp["cycle_life"] / 400)   # heavy use: cycles decide


def _day(n_days=2):
    """A sunny middle of the day, use in the morning and evening, evening price high."""
    gen = np.tile(np.r_[np.zeros(8), np.full(8, 5.0), np.zeros(8)], n_days)
    host = np.tile(np.r_[np.full(8, 0.5), np.full(8, 2.0), np.full(8, 1.5)], n_days)
    guest = np.tile(np.r_[np.full(8, 0.2), np.full(8, 0.5), np.full(8, 1.0)], n_days)
    price = np.tile(np.r_[np.full(8, 0.10), np.full(8, 0.08), np.full(8, 0.25)], n_days)
    spot = np.full(24 * n_days, 0.04)
    return gen, np.vstack([host, guest]), price, spot


def _run(kwh, **kw):
    gen, demand, price, spot = _day()
    b = {**bt.get("lfp"), "kwh": float(kwh)}
    flows = dispatch.simulate_year(gen, demand, price, spot, b, **kw)
    return gen, demand, price, spot, b, flows


def test_controller_conserves_energy_and_keeps_the_battery_in_bounds():
    gen, demand, price, spot, b, f = _run(20)
    usable = b["kwh"] * b["usable_share"]
    assert (f["soc"] >= -1e-9).all() and (f["soc"] <= usable + 1e-6).all()
    assert (f["charge"] <= b["kwh"] * b["c_rate"] + 1e-6).all()
    got = f["pv_to"] + f["bat_to"]
    assert (got <= demand + 1e-6).all()
    a = dispatch.account(f, gen, demand, price, spot, 0.10, ["host", "g"], b)   # asserts conservation inside
    assert a["wasted_kwh"] == pytest.approx(a["exported_kwh"] + a["curtailed_kwh"] + a["battery_losses_kwh"], abs=2)


def test_battery_never_charges_from_the_grid():
    gen, demand, price, spot, b, f = _run(20)
    assert (f["charge"][gen == 0] < 1e-9).all()                 # no sun -> no charging
    assert (f["charge"] <= gen + 1e-9).all()
    assert (f["pv_to"].sum(0) + f["charge"] <= gen + 1e-6).all()


def test_battery_moves_midday_surplus_to_the_dear_evening_and_wastes_less():
    *_, f0 = _run(0)
    gen, demand, price, spot, b, f = _run(20)
    assert f["bat_to"][:, price == 0.25].sum() > 0              # discharges in the evening
    a0 = dispatch.account(f0, gen, demand, price, spot, 0.10, ["host", "g"], {**b, "kwh": 0.0})
    a = dispatch.account(f, gen, demand, price, spot, 0.10, ["host", "g"], b)
    assert a["wasted_kwh"] < a0["wasted_kwh"]
    assert a["owner_total_eur"] > a0["owner_total_eur"]


def test_without_battery_the_host_is_served_first():
    gen, demand, *_ , f = _run(0)
    assert np.allclose(f["pv_to"][0], np.minimum(gen, demand[0]))


def test_no_guest_pays_more_than_the_grid():
    gen, demand, price, spot, b, f = _run(20, guest_discount=0.10)
    a = dispatch.account(f, gen, demand, price, spot, 0.10, ["host", "g"], b)
    g = a["per_building"]["g"]
    assert g["bill_with_roof_eur"] <= g["bill_grid_only_eur"]
    assert a["guests_saving_eur"] >= 0


def test_no_export_means_curtailment_not_export():
    gen, demand, price, spot = _day()
    b = {**bt.get("lfp"), "kwh": 0.0}
    f = dispatch.simulate_year(gen, demand, price, spot, b, export_limit=0.0)
    assert f["export"].sum() < 1e-9 and f["curtail"].sum() > 0


def test_screen_and_money():
    gen, demand, *_ = _day(1)
    s = screen(gen, demand[0])
    assert s["surplus_kwh"] == 24 and s["max_shiftable_kwh"] == 16      # 8 h x 3 kWh surplus; 4 + 12 kWh bought
    m = money({**bt.get("lfp"), "kwh": 10.0}, gain_eur=300.0, cycles=100)
    capex = 10 * bt.LFP_CAPEX_EUR_PER_KWH
    assert m["capex_eur"] == round(capex) and m["life_years"] == 15
    assert m["net_per_year_eur"] == round(300 - capex / 15 - capex * 0.025)
    assert m["break_even_eur_per_kwh"] == round(300 / (10 * (1 / 15 + 0.025)))


def test_price_model_beats_or_reports_against_baselines():
    pytest.importorskip("sklearn")
    from step06_prices_and_battery import price_model as pm
    hours = np.arange(np.datetime64("2023-01-01T00", "h"), np.datetime64("2026-01-01T00", "h"))
    rng = np.random.default_rng(0)
    local = (hours.astype(int) + 1) % 24
    v = 0.12 + 0.06 * np.sin(local / 24 * 2 * np.pi) + 0.01 * rng.standard_normal(len(hours))
    report, models, _ = pm.train_and_test({"PVPC": dict(zip(hours, v))}, horizons=(2,))
    r = report["horizons"]["2_days"]
    assert set(r) >= {"model", "same_hour_last_week", "typical_year", "model_beats_baselines"}
    assert r["model"]["mae"] < 0.02
