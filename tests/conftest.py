import pytest


@pytest.fixture(autouse=True)
def _no_auto_update(monkeypatch):
    monkeypatch.setenv("VDL_NO_AUTO_UPDATE", "1")
