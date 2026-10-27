"""Chronology, data failure and portfolio-accounting checks for the isolated lab."""
import importlib.util
import io
from pathlib import Path
import zipfile

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location("market_timing", Path(__file__).parents[1] / "scripts/research_lab/market_timing.py")
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


def archive(text):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("factors.csv", text)
    return stream.getvalue()


def test_parser_excludes_annual_rows_and_converts_percent():
    dates, data = lab.parse_french(archive("notes\n,Mkt-RF,SMB,HML,RF\n200001,1,2,3,0.1\n200002,-2,0,1,0.2\n\n2000,99,99,99,99"))
    assert dates.tolist() == ["200001", "200002"]
    assert data[0, 0] == .01
    assert data[0, 3] == .001


def test_real_source_repeats_header_for_annual_section():
    header = ",Mkt-RF,SMB,HML,RF\n"
    dates, _ = lab.parse_french(archive(header + "200001,1,2,3,0\n\nAnnual Factors\n" + header + "2000,99,99,99,99\n"))
    assert dates.tolist() == ["200001"]
    with pytest.raises(ValueError, match="ambiguous"):
        lab.parse_french(archive(header + "200001,1,2,3,0\n\n" + header + "200101,1,2,3,0\n"))


@pytest.mark.parametrize("tail", ["200003,1,2,3,0", "200001,1,2,3,0", "200002,-99.99,2,3,0", "200002,nan,2,3,0"])
def test_bad_source_is_not_silently_filled(tail):
    with pytest.raises(ValueError):
        lab.parse_french(archive("\n,Mkt-RF,SMB,HML,RF\n200001,1,2,3,0\n" + tail))


def test_future_data_cannot_change_prior_features_or_fixed_predictions():
    dates = np.array([f"{2000 + i // 12}{i % 12 + 1:02d}" for i in range(72)])
    data = np.random.default_rng(9).normal(0, .03, (72, 4))
    d, ends, x, y, _ = lab.feature_matrix(dates, data)
    assert all(lab.month_number(a) - lab.month_number(b) == 2 for a, b in zip(d, ends))
    model = lab.fit_ridge(x[:24], y[:24], 10)
    data2 = data.copy(); data2[60:] += .7
    d2, _, x2, y2, _ = lab.feature_matrix(dates, data2)
    mask = d2 <= dates[61]
    np.testing.assert_allclose(x[mask], x2[mask])
    np.testing.assert_allclose(lab.predict(model, x[mask]), lab.predict(model, x2[mask]))
    assert lab.fit_ridge(x2[:24], y2[:24], 10) == model


def test_cash_market_entry_and_switch_costs():
    ret, turnover = lab.simulate(np.array([1., 1., 0.]), np.array([.1, -.1, .2]), np.zeros(3), 10)
    np.testing.assert_allclose(turnover, [1, 0, 1])
    np.testing.assert_allclose(ret, [.999 * 1.1 - 1, -.1, -.001])
    cash, _ = lab.simulate(np.zeros(3), np.array([.1, -.1, .2]), np.full(3, .002), 10)
    np.testing.assert_allclose(cash, .002)


def test_half_portfolio_rebalances_drift_and_drawdown_includes_initial_loss():
    ret, turnover = lab.simulate(np.array([.5, .5]), np.array([.2, -.2]), np.zeros(2), 0)
    assert turnover[1] == pytest.approx(abs(.5 - .6 / 1.1))
    m = lab.metrics(np.array([-.1, .1]), np.zeros(2), np.zeros(2), np.ones(2))
    assert m["max_drawdown"] == pytest.approx(-.1)


def test_constant_label_has_constant_prediction():
    x = np.random.default_rng(8).normal(size=(40, 4))
    model = lab.fit_ridge(x, np.full(40, .01), 10)
    np.testing.assert_allclose(lab.predict(model, x * 20), .01)
