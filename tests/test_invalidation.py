"""Test the vector profile-memo invalidation wiring in tools/dataReaderTool.

Runs without QGIS: the qgis imports are stubbed so the real module can be
loaded, and a fake layer with fake signals drives the invalidation. Run with::

    python3 tests/test_invalidation.py
"""
import importlib.util
import os
import sys
import types

# --- stub the qgis surface the module imports at load time ---
qgis = types.ModuleType("qgis")
qgis_core = types.ModuleType("qgis.core")
qgis_pyqt = types.ModuleType("qgis.PyQt")
qgis_qtcore = types.ModuleType("qgis.PyQt.QtCore")
qgis_qtcore.QCoreApplication = object
qgis.core = qgis_core
qgis.PyQt = qgis_pyqt
sys.modules.update(
    {
        "qgis": qgis,
        "qgis.core": qgis_core,
        "qgis.PyQt": qgis_pyqt,
        "qgis.PyQt.QtCore": qgis_qtcore,
    }
)

# --- satisfy `from .utils import isProfilable` via a fake package ---
pkg = types.ModuleType("ptpkg")
pkg.__path__ = []
utils = types.ModuleType("ptpkg.utils")
utils.isProfilable = lambda *a, **k: False
sys.modules["ptpkg"] = pkg
sys.modules["ptpkg.utils"] = utils

PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tools",
    "dataReaderTool.py",
)
spec = importlib.util.spec_from_file_location("ptpkg.dataReaderTool", PATH)
mod = importlib.util.module_from_spec(spec)
mod.__package__ = "ptpkg"
sys.modules["ptpkg.dataReaderTool"] = mod
spec.loader.exec_module(mod)


class FakeSignal:
    def __init__(self):
        self._cbs = []

    def connect(self, cb):
        self._cbs.append(cb)

    def emit(self, *args):
        for cb in self._cbs:
            cb(*args)


class FakeLayer:
    def __init__(self, lid):
        self._id = lid
        for name in (
            "dataChanged",
            "attributeValueChanged",
            "geometryChanged",
            "featureAdded",
            "featuresDeleted",
            "willBeDeleted",
        ):
            setattr(self, name, FakeSignal())

    def id(self):
        return self._id


def _seed(lid):
    mod._VECTOR_PROFILE_CACHE[lid] = ("sig", ("prof", "buf", "multi"))


def test_data_change_signals_invalidate():
    lyr = FakeLayer("L1")
    mod._wireProfileCacheInvalidation(lyr)
    for sig, args in [
        ("dataChanged", ()),
        ("attributeValueChanged", (5, 2, 1.0)),
        ("geometryChanged", (5, None)),
        ("featureAdded", (5,)),
        ("featuresDeleted", ([5],)),
    ]:
        _seed("L1")
        getattr(lyr, sig).emit(*args)
        assert "L1" not in mod._VECTOR_PROFILE_CACHE, f"{sig} did not invalidate"


def test_wiring_is_idempotent():
    lyr = FakeLayer("L1b")
    mod._wireProfileCacheInvalidation(lyr)
    before = len(lyr.dataChanged._cbs)
    mod._wireProfileCacheInvalidation(lyr)
    assert len(lyr.dataChanged._cbs) == before


def test_will_be_deleted_invalidates_and_unwires():
    lyr = FakeLayer("L2")
    mod._wireProfileCacheInvalidation(lyr)
    _seed("L2")
    assert "L2" in mod._VECTOR_CACHE_WIRED
    lyr.willBeDeleted.emit()
    assert "L2" not in mod._VECTOR_PROFILE_CACHE
    assert "L2" not in mod._VECTOR_CACHE_WIRED


def test_invalidation_is_per_layer():
    la, lb = FakeLayer("A"), FakeLayer("B")
    mod._wireProfileCacheInvalidation(la)
    mod._wireProfileCacheInvalidation(lb)
    _seed("A")
    _seed("B")
    la.dataChanged.emit()
    assert "A" not in mod._VECTOR_PROFILE_CACHE
    assert "B" in mod._VECTOR_PROFILE_CACHE


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS: {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL: {name}: {exc}")
    print("\n" + ("ALL PASS" if not failures else f"{failures} FAILED"))
    sys.exit(1 if failures else 0)
