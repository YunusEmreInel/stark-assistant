"""Testler kullanıcının kendi ~/.stark/yerler.json dosyasına bağlı olmasın: örnek şehir İzmir."""
import pytest

from stark.tools import places


@pytest.fixture(autouse=True)
def example_districts(monkeypatch):
    monkeypatch.setattr(places, "DISTRICTS", {"İzmir": ["Bornova", "Karşıyaka", "Torbalı", "Çeşme", "Buca"]})
