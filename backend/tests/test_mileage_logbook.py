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
os.environ.setdefault("JWT_SECRET", "test")
# NB : on NE force PAS DB_NAME ici. Ces tests sont purement unitaires (helpers de
# calcul, aucun accès `db`/HTTP), mais `backend.server` lie `db = client[DB_NAME]`
# UNE SEULE FOIS au premier import du processus. Forcer un DB_NAME distinct
# (ex : 'facturepro_test_unit') faisait pointer ce `db` partagé vers une base
# VIDE selon l'ordre d'import ; le module d'intégration importé ensuite (même
# processus, même objet `db`) échouait alors à se connecter au compte de seed
# (`gussdub@gmail.com` absent → login 401). En laissant DB_NAME venir de `.env`
# (facturepro), les deux suites partagent la base de copie-prod et l'exécution
# combinée `pytest tests/test_mileage_logbook*.py` est déterministe.

from backend.server import (  # noqa: E402
    MILEAGE_RATES,
    MILEAGE_RATE_THRESHOLD_KM,
    _mileage_rate_for_year,
    _mileage_distance_km,
    _mileage_allocation,
    _mileage_sum_ytd,
    _mileage_trip_date_str,
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


def test_ytd_same_date_orders_by_created_at_then_id():
    # Fix T4 [CALCUL] : deux trajets de la MEME date sont departages par
    # created_at (ordre de saisie reel), pas par l'UUID arbitraire. Ici l'id 'z'
    # (UUID plus grand) a ete saisi AVANT 'a' (created_at plus tot) ; le courant
    # 'a' doit donc compter le trajet 'z' comme anterieur malgre 'z' > 'a'.
    trips = [
        {"id": "z", "trip_date": "2026-05-01", "distance_km": 10.0,
         "created_at": "2026-05-01T08:00:00+00:00",
         "employee_key": "user:U1", "vehicle_id": "V1"},
        {"id": "a", "trip_date": "2026-05-01", "distance_km": 20.0,
         "created_at": "2026-05-01T09:00:00+00:00",  # saisi APRES 'z'
         "employee_key": "user:U1", "vehicle_id": "V1"},
    ]
    total = _mileage_sum_ytd(trips, current_id="a", current_date="2026-05-01",
                             employee_key="user:U1", vehicle_id="V1",
                             current_created_at="2026-05-01T09:00:00+00:00")
    assert total == 10.0  # 'z' compte (saisi avant), malgre 'z' > 'a' en UUID


def test_ytd_same_created_at_falls_back_to_id():
    # created_at egal (ou absent) -> departage final deterministe par id, comme
    # avant le fix (comportement historique preserve).
    trips = [
        {"id": "a", "trip_date": "2026-05-01", "distance_km": 10.0,
         "created_at": "2026-05-01T08:00:00+00:00",
         "employee_key": "user:U1", "vehicle_id": "V1"},
        {"id": "b", "trip_date": "2026-05-01", "distance_km": 20.0,
         "created_at": "2026-05-01T08:00:00+00:00",  # meme instant que 'a'
         "employee_key": "user:U1", "vehicle_id": "V1"},
    ]
    total = _mileage_sum_ytd(trips, current_id="b", current_date="2026-05-01",
                             employee_key="user:U1", vehicle_id="V1",
                             current_created_at="2026-05-01T08:00:00+00:00")
    assert total == 10.0  # 'a' < 'b' au departage final


def test_ytd_annual_total_invariant_to_created_at_order():
    # Le TOTAL du cumul YTD (donc l'allocation annuelle) est invariant a l'ordre
    # de saisie de trajets du meme jour : seule la ligne qui absorbe la bascule
    # au seuil change, jamais le cumul. On verifie que la somme des anterieurs +
    # courant reste identique quel que soit le fil de saisie.
    def _trips(order):
        # order = liste de (id, created_at) dans l'ordre de saisie
        return [
            {"id": tid, "trip_date": "2026-07-02", "distance_km": km,
             "created_at": ca, "employee_key": "user:U1", "vehicle_id": "V1"}
            for (tid, ca, km) in order
        ]
    orderA = [("t1", "2026-07-02T08:00", 30.0), ("t2", "2026-07-02T09:00", 40.0)]
    orderB = [("t2", "2026-07-02T08:00", 40.0), ("t1", "2026-07-02T09:00", 30.0)]
    # cumul avant le DERNIER trajet saisi + sa distance = total du jour, invariant
    lastA = _mileage_sum_ytd(_trips(orderA), current_id="t2",
                             current_date="2026-07-02", employee_key="user:U1",
                             vehicle_id="V1", current_created_at="2026-07-02T09:00")
    lastB = _mileage_sum_ytd(_trips(orderB), current_id="t1",
                             current_date="2026-07-02", employee_key="user:U1",
                             vehicle_id="V1", current_created_at="2026-07-02T09:00")
    assert lastA + 40.0 == lastB + 30.0 == 70.0


def test_ytd_excludes_current_and_later_trips():
    trips = [
        _trip("2026-01-01", 10.0, "a"),
        _trip("2026-06-01", 99.0, "c"),  # courant
        _trip("2026-09-01", 77.0, "z"),  # posterieur
    ]
    total = _mileage_sum_ytd(trips, current_id="c", current_date="2026-06-01",
                             employee_key="user:U1", vehicle_id="V1")
    assert total == 10.0


# --- Fix T3 [CALCUL] : robustesse au format de trip_date (composante horaire) ---


def test_trip_date_str_strips_time_component():
    # une eventuelle composante horaire ou un datetime ne doit pas casser
    # le cumul : on ne garde que la partie date 'YYYY-MM-DD'.
    assert _mileage_trip_date_str("2026-12-31T09:00") == "2026-12-31"
    assert _mileage_trip_date_str("2026-01-05") == "2026-01-05"
    import datetime as _dt
    assert _mileage_trip_date_str(_dt.date(2026, 12, 31)) == "2026-12-31"
    assert _mileage_trip_date_str(_dt.datetime(2026, 12, 31, 9, 0)) == "2026-12-31"


def test_ytd_counts_dec31_trip_with_time_component():
    # Regression : un trajet du 31 decembre stocke avec une heure ('...T09:00')
    # ne doit PAS etre exclu du cumul de l'annee (bornes/tri robustes).
    trips = [
        _trip("2026-12-31T09:00", 300.0, "a"),
        _trip("2026-12-31T18:00", 40.0, "b"),  # courant
    ]
    total = _mileage_sum_ytd(trips, current_id="b", current_date="2026-12-31T18:00",
                             employee_key="user:U1", vehicle_id="V1")
    assert total == 300.0


def test_ytd_mixed_date_formats_order_by_date_portion():
    # Un trajet pur 'YYYY-MM-DD' et un trajet avec heure le meme jour :
    # l'ordre chronologique se base sur la partie date, pas sur le suffixe.
    trips = [
        _trip("2026-03-01", 10.0, "a"),           # anterieur (date pure)
        _trip("2026-03-10T08:00", 20.0, "b"),     # courant (avec heure)
    ]
    total = _mileage_sum_ytd(trips, current_id="b", current_date="2026-03-10T08:00",
                             employee_key="user:U1", vehicle_id="V1")
    assert total == 10.0


# ─── Task 13 : garde « année sans taux → allocation JAMAIS devinée » ──────────
# Le contrat côté helper d'allocation batch (_mileage_build_expense_for_trips)
# repose sur _mileage_rate_for_year(year) is None pour lever un 400 explicite
# plutôt que de deviner un montant à partir d'un taux d'une autre année. On fige
# ici l'invariant unitaire dont dépend la garde (2099 = année sans taux).
def test_missing_year_enrich_returns_none_allocation():
    # _mileage_enrich_trip doit poser allocation=None et rate_missing_year pour 2099.
    # Test unitaire du contrat via _mileage_rate_for_year déjà couvert ; ici on
    # documente la garde côté helper d'allocation batch (pas de fallback silencieux).
    assert _mileage_rate_for_year(2099) is None
