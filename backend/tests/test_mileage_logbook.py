"""Tests unitaires — Carnet de route (kilométrage), feature #13.

Task 1 : table des taux ARC + `_mileage_rate_for_year`.
Task 2 : distance dérivée + allocation avec split au seuil 5000 km.
Task 3 : cumul annuel `_mileage_sum_ytd`.
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
    _mileage_distance_km,
    _mileage_allocation,
    _mileage_sum_ytd,
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


# --- Task 2 : distance dérivée + allocation avec split au seuil ---


def test_distance_one_way():
    assert _mileage_distance_km(45.0, round_trip=False) == 45.0


def test_distance_round_trip_doubles():
    assert _mileage_distance_km(45.0, round_trip=True) == 90.0


def test_distance_rounds_two_decimals():
    assert _mileage_distance_km(10.005, round_trip=False) == 10.01
    assert _mileage_distance_km(33.333, round_trip=True) == 66.67


RATES_2026 = {"full": 0.73, "reduced": 0.67}


def test_allocation_no_switch_all_full():
    amount, bd = _mileage_allocation(100.0, ytd_before=0.0, rates=RATES_2026)
    assert amount == 73.00
    assert bd["km_full"] == 100.0
    assert bd["km_reduced"] == 0.0
    assert bd["rate_full"] == 0.73
    assert bd["rate_reduced"] == 0.67
    assert bd["ytd_before"] == 0.0


def test_allocation_all_reduced():
    amount, bd = _mileage_allocation(100.0, ytd_before=6000.0, rates=RATES_2026)
    assert amount == 67.00
    assert bd["km_full"] == 0.0
    assert bd["km_reduced"] == 100.0


def test_allocation_split_across_threshold():
    # cas critique : 4900 deja cumules, trajet 200 km -> 100 @ full + 100 @ reduced
    amount, bd = _mileage_allocation(200.0, ytd_before=4900.0, rates=RATES_2026)
    assert amount == 140.00
    assert bd["km_full"] == 100.0
    assert bd["km_reduced"] == 100.0


def test_allocation_exactly_at_threshold_all_reduced():
    amount, bd = _mileage_allocation(100.0, ytd_before=5000.0, rates=RATES_2026)
    assert amount == 67.00
    assert bd["km_full"] == 0.0
    assert bd["km_reduced"] == 100.0


def test_allocation_just_under_threshold_all_full():
    # ytd 4800 + 200 = pile 5000 -> tout au taux plein
    amount, bd = _mileage_allocation(200.0, ytd_before=4800.0, rates=RATES_2026)
    assert amount == round(200 * 0.73, 2)
    assert bd["km_full"] == 200.0
    assert bd["km_reduced"] == 0.0


# --- Task 3 : cumul annuel `_mileage_sum_ytd` ---


def _trip(trip_date, distance_km, tid, employee_key="user:U1", vehicle_id="V1"):
    return {
        "id": tid,
        "trip_date": trip_date,
        "distance_km": distance_km,
        "employee_key": employee_key,
        "vehicle_id": vehicle_id,
    }


def test_ytd_sums_earlier_trips_same_person_vehicle():
    trips = [
        _trip("2026-01-05", 100.0, "a"),
        _trip("2026-02-10", 50.0, "b"),
        _trip("2026-03-01", 30.0, "c"),  # le trajet courant
    ]
    total = _mileage_sum_ytd(trips, current_id="c", current_date="2026-03-01",
                             employee_key="user:U1", vehicle_id="V1")
    assert total == 150.0


def test_ytd_ignores_other_person():
    trips = [
        _trip("2026-01-05", 100.0, "a", employee_key="EMP2"),
        _trip("2026-02-01", 40.0, "b"),
    ]
    total = _mileage_sum_ytd(trips, current_id="b", current_date="2026-02-01",
                             employee_key="user:U1", vehicle_id="V1")
    assert total == 0.0


def test_ytd_ignores_other_vehicle():
    trips = [
        _trip("2026-01-05", 100.0, "a", vehicle_id="V2"),
        _trip("2026-02-01", 40.0, "b"),
    ]
    total = _mileage_sum_ytd(trips, current_id="b", current_date="2026-02-01",
                             employee_key="user:U1", vehicle_id="V1")
    assert total == 0.0


def test_ytd_ignores_other_year():
    trips = [
        _trip("2025-12-31", 500.0, "a"),
        _trip("2026-01-02", 40.0, "b"),
    ]
    total = _mileage_sum_ytd(trips, current_id="b", current_date="2026-01-02",
                             employee_key="user:U1", vehicle_id="V1")
    assert total == 0.0


def test_ytd_same_date_orders_by_id():
    trips = [
        _trip("2026-05-01", 10.0, "a"),
        _trip("2026-05-01", 20.0, "b"),  # courant ; 'a' < 'b' donc compte
    ]
    total = _mileage_sum_ytd(trips, current_id="b", current_date="2026-05-01",
                             employee_key="user:U1", vehicle_id="V1")
    assert total == 10.0


def test_ytd_excludes_current_and_later_trips():
    trips = [
        _trip("2026-01-01", 10.0, "a"),
        _trip("2026-06-01", 99.0, "c"),  # courant
        _trip("2026-09-01", 77.0, "z"),  # posterieur
    ]
    total = _mileage_sum_ytd(trips, current_id="c", current_date="2026-06-01",
                             employee_key="user:U1", vehicle_id="V1")
    assert total == 10.0
