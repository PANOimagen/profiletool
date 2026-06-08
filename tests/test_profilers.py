"""Tests for the profile y-value functions in tools/profilers.py.

These are pure numpy (no QGIS), so the module loads directly.

    pytest tests/test_profilers.py
"""
import importlib.util
import os

import numpy as np
import pytest


def _load_profilers():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "tools",
        "profilers.py",
    )
    spec = importlib.util.spec_from_file_location("profilers", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


profilers = _load_profilers()


def make_profile(x, z):
    return {"l": list(np.asarray(x, float)), "z": list(np.asarray(z, float))}


# --- height -----------------------------------------------------------------


def test_height_window_zero_returns_raw():
    x = [0, 1, 2, 3]
    z = [10, 12, 9, 15]
    hx, hy = profilers.height(make_profile(x, z), window=0)
    assert np.array_equal(hx, x)
    assert np.array_equal(hy, z)


def test_height_smoothing_preserves_constant():
    x = np.arange(100, dtype=float)
    z = np.full(100, 42.0)
    _, hy = profilers.height(make_profile(x, z), window=10)
    assert np.allclose(hy, 42.0)


def test_height_smoothing_reduces_noise():
    rng = np.random.default_rng(0)
    x = np.arange(1000, dtype=float)
    z = 100 + rng.normal(0, 5, 1000)
    _, raw = profilers.height(make_profile(x, z), window=0)
    _, smoothed = profilers.height(make_profile(x, z), window=50)
    assert np.std(smoothed) < np.std(raw)


# --- slopes_pct -------------------------------------------------------------


def test_slope_of_straight_line_is_exact():
    # z = 0.05*x -> 5% grade everywhere; least squares on a line is exact
    x = np.arange(0, 2001, dtype=float)
    z = 0.05 * x + 7
    _, slope = profilers.slopes_pct(make_profile(x, z), window=1000)
    assert np.allclose(slope, 5.0)


def test_slope_of_flat_profile_is_zero():
    x = np.arange(0, 500, dtype=float)
    z = np.full_like(x, 30.0)
    _, slope = profilers.slopes_pct(make_profile(x, z), window=200)
    assert np.allclose(slope, 0.0)


def test_slope_window_zero_is_adjacent_difference():
    x = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    z = 0.05 * x
    _, slope = profilers.slopes_pct(make_profile(x, z), window=0)
    assert np.allclose(slope, 5.0)


def test_slope_window_zero_handles_zero_spacing():
    # duplicate distance (dx = 0) must not yield inf/nan in the output
    x = np.array([0.0, 0.0, 1.0, 2.0])
    z = np.array([0.0, 1.0, 2.0, 3.0])
    _, slope = profilers.slopes_pct(make_profile(x, z), window=0)
    assert np.all(np.isfinite(slope))


def test_slope_smoothing_reduces_spikes():
    # bunched, jittery points: a window tames the adjacent-point spikes
    rng = np.random.default_rng(2)
    x = np.cumsum(np.abs(rng.normal(5, 4, 2000)))
    z = 0.02 * x + rng.normal(0, 1.0, 2000)
    _, raw = profilers.slopes_pct(make_profile(x, z), window=0)
    _, windowed = profilers.slopes_pct(make_profile(x, z), window=500)
    assert np.abs(windowed).max() < np.abs(raw).max()


# --- slopes_deg -------------------------------------------------------------


def test_slope_deg_of_45_degree_grade():
    x = np.arange(0, 1001, dtype=float)
    z = x.copy()  # 100% grade -> 45 degrees
    _, deg = profilers.slopes_deg(make_profile(x, z), window=500)
    assert np.allclose(deg, 45.0)


def test_slope_deg_consistent_with_pct():
    rng = np.random.default_rng(1)
    x = np.cumsum(rng.uniform(1, 3, 500))
    z = np.sin(x / 50) * 20 + rng.normal(0, 0.5, 500)
    p = make_profile(x, z)
    _, pct = profilers.slopes_pct(p, window=100)
    _, deg = profilers.slopes_deg(p, window=100)
    assert np.allclose(deg, np.degrees(np.arctan(pct / 100.0)))


# --- _windowed_mean ---------------------------------------------------------


def test_windowed_mean_window_zero_is_identity():
    x = np.arange(10, dtype=float)
    y = np.arange(10, dtype=float) * 3
    assert np.array_equal(profilers._windowed_mean(x, y, 0), y)


def test_windowed_mean_centred_average():
    # evenly spaced points, window covering exactly the 3 centre points
    x = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    y = np.array([0.0, 0.0, 9.0, 0.0, 0.0])
    out = profilers._windowed_mean(x, y, window=2.0)
    assert out[2] == pytest.approx(3.0)  # mean of [0, 9, 0]


# --- edge cases -------------------------------------------------------------


@pytest.mark.parametrize("fn_name", ["height", "slopes_pct", "slopes_deg"])
def test_single_point_does_not_crash(fn_name):
    x, y = getattr(profilers, fn_name)(make_profile([0.0], [5.0]), window=100)
    assert len(x) == 1
    assert len(y) == 1
