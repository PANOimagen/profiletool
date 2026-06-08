"""Tests for the vector profile-cache invalidation wiring in dataReaderTool.

Runs without QGIS: the qgis imports are stubbed so the real module can be
loaded, then a fake layer with fake signals drives the invalidation.

    pytest tests/test_invalidation.py
"""
import importlib.util
import os
import sys
import types

import pytest


def _load_datareadertool():
    """Import tools/dataReaderTool with the qgis surface stubbed out."""
    qgis = types.ModuleType("qgis")
    qgis.core = types.ModuleType("qgis.core")
    qgis.PyQt = types.ModuleType("qgis.PyQt")
    qtcore = types.ModuleType("qgis.PyQt.QtCore")
    qtcore.QCoreApplication = object
    sys.modules.update(
        {
            "qgis": qgis,
            "qgis.core": qgis.core,
            "qgis.PyQt": qgis.PyQt,
            "qgis.PyQt.QtCore": qtcore,
        }
    )

    # satisfy `from .utils import isProfilable` via a fake package
    pkg = types.ModuleType("ptpkg")
    pkg.__path__ = []
    utils = types.ModuleType("ptpkg.utils")
    utils.isProfilable = lambda *a, **k: False
    sys.modules["ptpkg"] = pkg
    sys.modules["ptpkg.utils"] = utils

    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "tools",
        "dataReaderTool.py",
    )
    spec = importlib.util.spec_from_file_location("ptpkg.dataReaderTool", path)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "ptpkg"
    sys.modules["ptpkg.dataReaderTool"] = mod
    spec.loader.exec_module(mod)
    return mod


dataReaderTool = _load_datareadertool()

RESULT = ("prof", "buf", "multi")
SIG = ("sig",)

# (signal name, emit args) for every layer signal that should drop the cache
DATA_CHANGE_SIGNALS = [
    ("dataChanged", ()),
    ("attributeValueChanged", (5, 2, 1.0)),
    ("geometryChanged", (5, None)),
    ("featureAdded", (5,)),
    ("featuresDeleted", ([5],)),
]


class FakeSignal:
    """Minimal stand-in for a Qt signal: connect callbacks, emit to call them."""

    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in self.callbacks:
            callback(*args)


class FakeLayer:
    SIGNALS = (
        "dataChanged",
        "attributeValueChanged",
        "geometryChanged",
        "featureAdded",
        "featuresDeleted",
        "willBeDeleted",
    )

    def __init__(self, layer_id="L1"):
        self._id = layer_id
        for name in self.SIGNALS:
            setattr(self, name, FakeSignal())

    def id(self):
        return self._id


@pytest.fixture
def cache():
    return dataReaderTool.ProfileCache()


@pytest.fixture
def layer():
    return FakeLayer()


@pytest.mark.parametrize("signal, args", DATA_CHANGE_SIGNALS)
def test_data_change_signals_invalidate(cache, layer, signal, args):
    cache.put(layer, SIG, RESULT)
    assert cache.get(layer, SIG) == RESULT
    getattr(layer, signal).emit(*args)
    assert cache.get(layer, SIG) is None


def test_get_misses_on_different_signature(cache, layer):
    cache.put(layer, ("sigA",), RESULT)
    assert cache.get(layer, ("sigB",)) is None
    assert cache.get(layer, ("sigA",)) == RESULT


def test_wiring_is_idempotent(cache, layer):
    cache.put(layer, SIG, RESULT)
    before = len(layer.dataChanged.callbacks)
    cache.put(layer, ("sig2",), RESULT)  # re-put must not re-wire
    assert len(layer.dataChanged.callbacks) == before


def test_will_be_deleted_invalidates_and_unwires(cache, layer):
    cache.put(layer, SIG, RESULT)
    assert layer.id() in cache._wired
    layer.willBeDeleted.emit()
    assert cache.get(layer, SIG) is None
    assert layer.id() not in cache._wired


def test_invalidation_is_per_layer(cache):
    a, b = FakeLayer("A"), FakeLayer("B")
    cache.put(a, SIG, RESULT)
    cache.put(b, SIG, RESULT)
    a.dataChanged.emit()
    assert cache.get(a, SIG) is None
    assert cache.get(b, SIG) == RESULT
