"""Tests unitaires — Carnet de route (kilométrage), feature #13.

Task 1 : table des taux ARC + `_mileage_rate_for_year`.
"""
import os
import sys

# Le module server.py se connecte à Mongo au chargement (db = client[DB_NAME]),
# donc DB_NAME doit exister avant l'import. On rend aussi le paquet `backend`
# importable depuis la racine du dépôt pour `from backend.server import ...`.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "facturepro_test_unit")
os.environ.setdefault("JWT_SECRET", "test")

from backend.server import (  # noqa: E402
    MILEAGE_RATES,
    MILEAGE_RATE_THRESHOLD_KM,
    _mileage_rate_for_year,
)


def test_mileage_rate_for_year_known_years():
    assert _mileage_rate_for_year(2024) == {"full": 0.70, "reduced": 0.64}
    assert _mileage_rate_for_year(2025) == {"full": 0.72, "reduced": 0.66}
    assert _mileage_rate_for_year(2026) == {"full": 0.73, "reduced": 0.67}


def test_mileage_rate_for_year_missing_returns_none():
    assert _mileage_rate_for_year(1999) is None
    assert _mileage_rate_for_year(2099) is None


def test_mileage_rate_for_year_accepts_string_year():
    assert _mileage_rate_for_year("2026") == {"full": 0.73, "reduced": 0.67}


def test_mileage_threshold_constant():
    assert MILEAGE_RATE_THRESHOLD_KM == 5000
