"""The demand-model trainer, on made-up meters in the GoiEner layout (the real files were not available offline)."""
import numpy as np
import pandas as pd
import pytest

from step05_forecast_demand import train_profile_model as tp


def test_cnae_groups():
    assert tp.cnae_group("9820") == "household" and tp.cnae_group("85.10") == "education"
    assert tp.cnae_group(8411) == "public_admin" and tp.cnae_group("") == "other" and tp.cnae_group(None) == "other"


@pytest.fixture
def meters(tmp_path):
    rng = np.random.default_rng(1)
    hours = pd.date_range("2021-01-01", "2021-12-31 23:00", freq="h", tz="UTC")
    local = hours.tz_convert(tp.TZ)
    rows = []
    for i in range(30):
        office = i % 2 == 0
        kw = rng.uniform(3, 10)
        if office:   # busy 8-18 on weekdays, small at night
            load = np.where((local.hour >= 8) & (local.hour < 18) & (local.dayofweek < 5), 1.0, 0.15)
        else:        # evening peak, every day
            load = np.where((local.hour >= 19) & (local.hour < 23), 1.0, 0.3)
        kwh = kw * 0.1 * load * (1 + 0.05 * rng.standard_normal(len(hours)))
        pd.DataFrame({"timestamp": hours.strftime("%Y-%m-%d %H:%M:%S+00:00"), "kWh": kwh}).to_csv(tmp_path / f"u{i}.csv", index=False)
        rows.append({"user": f"u{i}", "cnae": "6201" if office else "9820", "p1": kw})
    pd.DataFrame(rows).to_csv(tmp_path / "metadata.csv", index=False)
    return tmp_path


def test_tables_and_model(meters, tmp_path):
    out = tmp_path / "out"
    rep = tp.run(meters / "metadata.csv", meters, out)
    assert set(rep["supply_points_per_type"]) == {"office", "household"}
    assert rep["model_beats_baseline"] or rep["model_mae_kwh_day"] < 1.5 * rep["baseline_mae_kwh_day"]
    shape = pd.read_csv(out / "hourly_shape.csv")
    sums = shape.groupby(["btype", "season", "weekend"]).share.sum()
    assert np.allclose(sums, 1.0, atol=1e-3)
    mid = shape[(shape.btype == "office") & (shape.weekend == 0) & (shape.season == "summer")].set_index("hour").share
    assert mid.loc[12] > 3 * mid.loc[3]          # offices: busy at noon, quiet at 3 am
    d = pd.read_csv(out / "daily_averages.csv")
    off = d[(d.btype == "office") & (d.month == 6)].set_index("weekend").kwh_day_mean
    assert off.loc[0] > off.loc[1]               # offices use more on weekdays


def test_missing_column_message(tmp_path):
    pd.DataFrame({"a": [1]}).to_csv(tmp_path / "metadata.csv", index=False)
    with pytest.raises(SystemExit, match="No 'id' column"):
        tp.collect(tmp_path / "metadata.csv", tmp_path)


def test_learned_shapes_follow_the_data(meters, tmp_path):
    from step05_forecast_demand import baseline_profiles as bp
    tp.run(meters / "metadata.csv", meters, tmp_path / "m")
    t = np.arange(np.datetime64("2021-01-01T00:00"), np.datetime64("2022-01-01T00:00"), np.timedelta64(1, "h"))
    sh = bp.profile_shapes(t, profile_path=None, model_dir=tmp_path / "m")
    assert set(sh) == {"home", "shop", "office", "school"}
    assert abs(sh["office"].sum() - 1) < 1e-9 and (sh["office"] >= 0).all()
    hour, wd, _ = bp.local_hours(t)
    assert sh["office"][(hour == 12) & (wd < 5)].mean() > 3 * sh["office"][(hour == 3) & (wd < 5)].mean()
    assert sh["office"][wd < 5].mean() > sh["office"][wd >= 5].mean()


def test_compare_with_barcelona_profile(tmp_path):
    import json
    from step05_forecast_demand import compare_with_bcn as cb
    hs = [{"btype": t, "season": s, "weekend": w, "hour": h, "share": 1 / 24}
          for t in ("household", "retail") for s in ("winter", "spring", "summer", "autumn") for w in (0, 1) for h in range(24)]
    da = [{"btype": t, "month": m, "weekend": w, "kwh_day_mean": 10 + m * (1 - w) + 5 * w}
          for t in ("household", "retail") for m in range(1, 13) for w in (0, 1)]
    pd.DataFrame(hs).to_csv(tmp_path / "hourly_shape.csv", index=False)
    pd.DataFrame(da).to_csv(tmp_path / "daily_averages.csv", index=False)
    prof = {k: {"band_share": {"weekday": [.25] * 4, "weekend": [.25] * 4}, "weekend_vs_weekday": 0.8,
                "month_factor": [1 + m / 100 for m in range(12)]} for k in ("home", "shop")}
    (tmp_path / "p.json").write_text(json.dumps(prof))
    out = cb.compare(tmp_path / "p.json", tmp_path)
    assert list(out.type)[0] == "Barcelona home" and out["month correlation"].min() > 0.9
