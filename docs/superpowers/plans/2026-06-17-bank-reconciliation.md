# Bank Reconciliation (feature #7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre l'import d'un relevé CSV bancaire et le rapprochement avec factures (auto-création de payment feature #6) et dépenses (auto-lien). Page dédiée, mapping configurable, persistance complète.

**Architecture:** Backend FastAPI + pymongo sync — code dans `backend/server.py` (gros fichier monolithique, pattern établi). Trois nouvelles collections (`bank_mappings`, `bank_imports`, `bank_transactions`). Frontend React 18 CRA, page + 5 composants. Tests pytest + fixture `auth` (pattern miroir de `test_partial_payments_integration.py`).

**Tech Stack:** Python 3.11 (csv stdlib, hashlib), FastAPI, pymongo. React 18 CRA, axios, lucide-react. MongoDB Atlas (prod) / localhost:27017 (dev).

**Spec source:** [docs/superpowers/specs/2026-06-17-bank-reconciliation-design.md](../specs/2026-06-17-bank-reconciliation-design.md)

---

## File Structure

**Backend** (`backend/server.py` — section dédiée ajoutée après les helpers feature #6) :
- Helpers parsing : `_sanitize_cell`, `_parse_csv_date`, `_normalize_amount`, `_compute_file_hash`, `_parse_csv_rows`
- Helpers match : `_auto_match_transactions`, `_apply_match`, `_release_bank_transaction`, `_get_invoice_outstanding`
- Endpoints : `/api/bank/mappings`, `/api/bank/imports`, `/api/bank/transactions/{tx_id}/*`
- Modifications cascade : `DELETE /api/invoices/{id}`, `DELETE /api/invoices/{id}/payments/{pid}`, `DELETE /api/expenses/{id}`

**Tests** (`backend/tests/`) :
- `test_bank_reconciliation.py` — unitaires (parsers + match algo)
- `test_bank_reconciliation_integration.py` — intégration HTTP

**Frontend** (`frontend/src/`) :
- `pages/BankReconciliationPage.js` — page principale (liste imports + routes internes vers wizard / matching)
- `components/BankImportWizard.js` — wizard 2 étapes (upload + mapping)
- `components/BankMatchingScreen.js` — écran de matching (3ᵉ étape post-import)
- `components/BankCreateExpenseModal.js` — modal "Créer dépense depuis ligne"
- `components/BankCreateInvoiceModal.js` — modal "Créer facture depuis ligne"
- `components/BankManualSearchModal.js` — modal "Chercher manuellement"
- Modifications : `pages/SettingsPage.js` ou `Layout.js` (entrée sidebar) + `App.js` (routing)

---

## Task 0 : Setup (créer fichiers de tests vides)

**Files:**
- Create: `backend/tests/test_bank_reconciliation.py`
- Create: `backend/tests/test_bank_reconciliation_integration.py`

- [ ] **Step 1: Créer les deux fichiers vides avec imports**

`backend/tests/test_bank_reconciliation.py` :
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from server import (
    _sanitize_cell,
    _parse_csv_date,
    _normalize_amount,
    _compute_file_hash,
)
```

`backend/tests/test_bank_reconciliation_integration.py` :
```python
import os
import uuid
import requests
import pytest

BASE_URL = "http://localhost:8000"

@pytest.fixture(scope="module")
def auth():
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "gussdub@gmail.com", "password": "testpass123"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/tests/test_bank_reconciliation.py backend/tests/test_bank_reconciliation_integration.py
git commit -m "test(bank): stub test files for feature #7"
```

---

## Task 1 : Helpers parsing CSV (unitaires)

**Files:**
- Modify: `backend/server.py` (ajouter une section après les helpers feature #6 ~ligne 480)
- Test: `backend/tests/test_bank_reconciliation.py`

- [ ] **Step 1: Écrire les tests unitaires**

Ajouter à `backend/tests/test_bank_reconciliation.py` :
```python
class TestSanitizeCell:
    def test_strip_equals(self):
        assert _sanitize_cell("=cmd|...") == "cmd|..."
    def test_strip_plus(self):
        assert _sanitize_cell("+33-1") == "33-1"
    def test_strip_minus(self):
        assert _sanitize_cell("-1234") == "1234"
    def test_strip_at(self):
        assert _sanitize_cell("@mention") == "mention"
    def test_strip_leading_tab(self):
        assert _sanitize_cell("\tdata") == "data"
    def test_preserves_leading_space_then_strips(self):
        # whitespace before = is also stripped
        assert _sanitize_cell("  =evil") == "evil"
    def test_normal_value(self):
        assert _sanitize_cell("hello world") == "hello world"
    def test_empty(self):
        assert _sanitize_cell("") == ""
    def test_none_safe(self):
        assert _sanitize_cell(None) == ""

class TestParseCsvDate:
    def test_iso(self):
        assert _parse_csv_date("2026-03-14", "YYYY-MM-DD") == "2026-03-14"
    def test_dmy(self):
        assert _parse_csv_date("14/03/2026", "DD/MM/YYYY") == "2026-03-14"
    def test_mdy(self):
        assert _parse_csv_date("03/14/2026", "MM/DD/YYYY") == "2026-03-14"
    def test_invalid(self):
        assert _parse_csv_date("not a date", "YYYY-MM-DD") is None
    def test_empty(self):
        assert _parse_csv_date("", "YYYY-MM-DD") is None
    def test_wrong_format(self):
        # 14/03/2026 parsed as MM/DD/YYYY → invalid (month 14)
        assert _parse_csv_date("14/03/2026", "MM/DD/YYYY") is None

class TestNormalizeAmount:
    def test_us(self):
        assert _normalize_amount("1,234.56") == 1234.56
    def test_eu(self):
        assert _normalize_amount("1 234,56") == 1234.56
    def test_nbsp(self):
        # non-breaking space U+00A0
        assert _normalize_amount("1 234,56") == 1234.56
    def test_negative(self):
        assert _normalize_amount("-99.50") == -99.50
    def test_plain_int(self):
        assert _normalize_amount("100") == 100.0
    def test_empty(self):
        assert _normalize_amount("") is None
    def test_invalid(self):
        assert _normalize_amount("abc") is None
    def test_only_dot(self):
        assert _normalize_amount("100.") == 100.0
    def test_only_comma_decimal(self):
        assert _normalize_amount("0,50") == 0.50

class TestComputeFileHash:
    def test_deterministic(self):
        a = _compute_file_hash(b"hello,world\n1,2\n")
        b = _compute_file_hash(b"hello,world\n1,2\n")
        assert a == b
        assert len(a) == 64  # sha256 hex
    def test_crlf_lf_same(self):
        # CRLF and LF normalized to same hash for robustness across exports
        a = _compute_file_hash(b"hello,world\r\n1,2\r\n")
        b = _compute_file_hash(b"hello,world\n1,2\n")
        assert a == b
    def test_different_content_different_hash(self):
        a = _compute_file_hash(b"x")
        b = _compute_file_hash(b"y")
        assert a != b
```

- [ ] **Step 2: Lancer pour confirmer l'échec**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
pytest tests/test_bank_reconciliation.py -v 2>&1 | tail -20
```
Attendu : ImportError sur `_sanitize_cell` (n'existe pas encore).

- [ ] **Step 3: Implémenter les 4 helpers**

Ajouter dans `backend/server.py` après les helpers feature #6 (chercher la dernière fonction `_enrich_invoice` et insérer après) :

```python
# ─── Bank reconciliation helpers (feature #7) ───
import csv as csv_module
import io
import hashlib
from datetime import datetime, timedelta

_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t")

def _sanitize_cell(value):
    """Strippe les caractères d'injection CSV en début de cellule (=, +, -, @, tab)."""
    if value is None:
        return ""
    stripped = value.lstrip()
    if stripped and stripped[0] in _CSV_INJECTION_PREFIXES:
        return stripped[1:]
    return value

_DATE_FORMAT_MAP = {
    "YYYY-MM-DD": "%Y-%m-%d",
    "DD/MM/YYYY": "%d/%m/%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
}

def _parse_csv_date(value, fmt):
    """Parse une cellule de date selon le format demandé. Retourne 'YYYY-MM-DD' ou None."""
    if not value:
        return None
    py_fmt = _DATE_FORMAT_MAP.get(fmt)
    if not py_fmt:
        return None
    try:
        dt = datetime.strptime(value.strip(), py_fmt)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return None

def _normalize_amount(value):
    """Parse un montant avec notation US (1,234.56) ou EU (1 234,56). Retourne float ou None."""
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    # supprime espaces normaux et non-cassants
    s = s.replace(" ", "").replace(" ", "")
    # heuristique : si présence de virgule mais pas de point → virgule = décimal (EU)
    # si les deux → point = décimal (US), virgules = milliers
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    elif "," in s and "." in s:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None

def _compute_file_hash(data):
    """sha256 hex du contenu — normalise CRLF → LF pour cohérence inter-export."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    normalized = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()
```

- [ ] **Step 4: Lancer les tests pour confirmer pass**

```bash
pytest tests/test_bank_reconciliation.py -v 2>&1 | tail -25
```
Attendu : 24 tests pass (les 4 classes).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_bank_reconciliation.py
git commit -m "feat(bank): helpers parsing CSV (sanitize/date/amount/hash) + tests"
```

---

## Task 2 : Helper de parsing complet `_parse_csv_rows`

**Files:**
- Modify: `backend/server.py` (suite des helpers bancaires)
- Test: `backend/tests/test_bank_reconciliation.py`

- [ ] **Step 1: Écrire les tests unitaires**

Ajouter à `backend/tests/test_bank_reconciliation.py` (après les classes existantes) :
```python
from server import _parse_csv_rows

class TestParseCsvRows:
    def _mapping(self, **overrides):
        m = {
            "delimiter": ",", "has_header": True,
            "date_column": 0, "date_format": "YYYY-MM-DD",
            "description_column": 1,
            "amount_mode": "single", "amount_column": 2,
            "debit_column": None, "credit_column": None,
            "sign_convention": "positive_is_credit",
        }
        m.update(overrides)
        return m

    def test_simple_csv(self):
        csv_text = "date,desc,amount\n2026-03-14,Costco,-127.84\n2026-03-15,Client X,250.00\n"
        rows = _parse_csv_rows(csv_text.encode(), self._mapping())
        assert len(rows) == 2
        assert rows[0]["date"] == "2026-03-14"
        assert rows[0]["description"] == "Costco"
        assert rows[0]["amount_cad"] == -127.84
        assert rows[0]["parse_error"] is False
        assert rows[1]["amount_cad"] == 250.00

    def test_no_header(self):
        csv_text = "2026-03-14,Costco,-100\n"
        rows = _parse_csv_rows(csv_text.encode(), self._mapping(has_header=False))
        assert len(rows) == 1
        assert rows[0]["description"] == "Costco"

    def test_semicolon_delimiter(self):
        csv_text = "date;desc;amount\n2026-03-14;Costco;-127.84\n"
        rows = _parse_csv_rows(csv_text.encode(), self._mapping(delimiter=";"))
        assert len(rows) == 1
        assert rows[0]["amount_cad"] == -127.84

    def test_eu_amount(self):
        csv_text = "date,desc,amount\n14/03/2026,Costco,-1 234,56\n"
        rows = _parse_csv_rows(csv_text.encode(),
                                self._mapping(date_format="DD/MM/YYYY"))
        # NB: cellule contient virgule → impossible avec delimiter virgule.
        # On utilise donc semicolon ici.
        csv_text = "date;desc;amount\n14/03/2026;Costco;-1 234,56\n"
        rows = _parse_csv_rows(csv_text.encode(),
                                self._mapping(delimiter=";",
                                              date_format="DD/MM/YYYY"))
        assert rows[0]["amount_cad"] == -1234.56

    def test_debit_credit_mode_credit(self):
        m = self._mapping(amount_mode="debit_credit", amount_column=None,
                          debit_column=2, credit_column=3)
        csv_text = "date,desc,debit,credit\n2026-03-14,Salary,,1500.00\n"
        rows = _parse_csv_rows(csv_text.encode(), m)
        assert rows[0]["amount_cad"] == 1500.00

    def test_debit_credit_mode_debit(self):
        m = self._mapping(amount_mode="debit_credit", amount_column=None,
                          debit_column=2, credit_column=3)
        csv_text = "date,desc,debit,credit\n2026-03-14,Fee,3.95,\n"
        rows = _parse_csv_rows(csv_text.encode(), m)
        assert rows[0]["amount_cad"] == -3.95

    def test_debit_credit_both_filled(self):
        m = self._mapping(amount_mode="debit_credit", amount_column=None,
                          debit_column=2, credit_column=3)
        csv_text = "date,desc,debit,credit\n2026-03-14,X,100,5\n"
        rows = _parse_csv_rows(csv_text.encode(), m)
        # credit - debit = 5 - 100 = -95
        assert rows[0]["amount_cad"] == -95.0

    def test_sign_convention_positive_is_debit(self):
        m = self._mapping(sign_convention="positive_is_debit")
        csv_text = "date,desc,amount\n2026-03-14,Costco,100\n"
        rows = _parse_csv_rows(csv_text.encode(), m)
        # positive in CSV → debit → amount_cad negative
        assert rows[0]["amount_cad"] == -100.0

    def test_skip_empty_rows(self):
        csv_text = "date,desc,amount\n2026-03-14,A,1\n\n2026-03-15,B,2\n"
        rows = _parse_csv_rows(csv_text.encode(), self._mapping())
        assert len(rows) == 2  # ligne vide ignorée
        assert rows[0]["description"] == "A"
        assert rows[1]["description"] == "B"

    def test_parse_error_invalid_date(self):
        csv_text = "date,desc,amount\nnot-a-date,X,100\n"
        rows = _parse_csv_rows(csv_text.encode(), self._mapping())
        assert rows[0]["parse_error"] is True
        assert rows[0]["date"] is None

    def test_parse_error_invalid_amount(self):
        csv_text = "date,desc,amount\n2026-03-14,X,foo\n"
        rows = _parse_csv_rows(csv_text.encode(), self._mapping())
        assert rows[0]["parse_error"] is True
        assert rows[0]["amount_cad"] is None

    def test_row_limit_5001(self):
        # 5001 data rows (+ header) doit lever ValueError
        lines = ["date,desc,amount"] + [f"2026-03-14,X,{i}" for i in range(5001)]
        csv_text = "\n".join(lines) + "\n"
        with pytest.raises(ValueError, match="row limit"):
            _parse_csv_rows(csv_text.encode(), self._mapping())

    def test_sanitization_applied(self):
        csv_text = "date,desc,amount\n2026-03-14,=cmd|attack,100\n"
        rows = _parse_csv_rows(csv_text.encode(), self._mapping())
        assert rows[0]["description"] == "cmd|attack"

    def test_raw_line_only_when_parse_error(self):
        csv_text = "date,desc,amount\n2026-03-14,Costco,100\nbad,X,nope\n"
        rows = _parse_csv_rows(csv_text.encode(), self._mapping())
        assert rows[0].get("raw_line") is None
        assert rows[1]["raw_line"] is not None
        assert "bad" in rows[1]["raw_line"]
```

- [ ] **Step 2: Lancer pour confirmer l'échec**

```bash
pytest tests/test_bank_reconciliation.py::TestParseCsvRows -v 2>&1 | tail -10
```
Attendu : ImportError.

- [ ] **Step 3: Implémenter `_parse_csv_rows`**

Ajouter dans `backend/server.py` après les helpers de Task 1 :

```python
ROW_LIMIT = 5000

def _parse_csv_rows(csv_bytes, mapping):
    """Parse les lignes CSV selon le mapping. Retourne liste de dicts.
    Lève ValueError("row limit") si > ROW_LIMIT lignes de données.
    Chaque dict : {row_index, date, description, amount_cad, parse_error, raw_line(opt)}.
    """
    text = csv_bytes.decode("utf-8", errors="replace")
    reader = csv_module.reader(io.StringIO(text), delimiter=mapping["delimiter"])
    out = []
    data_index = 0
    skip_header = mapping.get("has_header", True)
    for raw_row in reader:
        # skip lignes vides
        if not raw_row or all((c or "").strip() == "" for c in raw_row):
            continue
        if skip_header:
            skip_header = False
            continue
        if data_index >= ROW_LIMIT:
            raise ValueError(f"CSV exceeds row limit ({ROW_LIMIT})")
        sanitized = [_sanitize_cell(c) for c in raw_row]
        date_str = sanitized[mapping["date_column"]] if mapping["date_column"] < len(sanitized) else ""
        desc = sanitized[mapping["description_column"]] if mapping["description_column"] < len(sanitized) else ""
        date_parsed = _parse_csv_date(date_str, mapping["date_format"])
        # amount
        amount = None
        if mapping["amount_mode"] == "single":
            col = mapping.get("amount_column")
            if col is not None and col < len(sanitized):
                amt = _normalize_amount(sanitized[col])
                if amt is not None:
                    if mapping.get("sign_convention") == "positive_is_debit":
                        amt = -amt
                amount = amt
        else:  # debit_credit
            dcol = mapping.get("debit_column")
            ccol = mapping.get("credit_column")
            d = _normalize_amount(sanitized[dcol]) if (dcol is not None and dcol < len(sanitized)) else None
            c = _normalize_amount(sanitized[ccol]) if (ccol is not None and ccol < len(sanitized)) else None
            d = abs(d) if d is not None else 0
            c = abs(c) if c is not None else 0
            if d == 0 and c == 0:
                amount = 0.0
            else:
                amount = c - d
        parse_error = (date_parsed is None) or (amount is None)
        row_dict = {
            "row_index": data_index,
            "date": date_parsed,
            "description": desc[:500],
            "amount_cad": round(amount, 2) if amount is not None else None,
            "parse_error": parse_error,
        }
        if parse_error:
            row_dict["raw_line"] = (mapping["delimiter"].join(raw_row))[:500]
        else:
            row_dict["raw_line"] = None
        out.append(row_dict)
        data_index += 1
    return out
```

- [ ] **Step 4: Lancer les tests**

```bash
pytest tests/test_bank_reconciliation.py -v 2>&1 | tail -20
```
Attendu : 38 tests pass (24 Task 1 + 14 Task 2).

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_bank_reconciliation.py
git commit -m "feat(bank): _parse_csv_rows avec gestion debit_credit + sanitization + tests"
```

---

## Task 3 : Endpoints GET/POST `/api/bank/mappings`

**Files:**
- Modify: `backend/server.py` (ajouter section endpoints bancaires)
- Test: `backend/tests/test_bank_reconciliation_integration.py`

- [ ] **Step 1: Écrire les tests d'intégration**

Ajouter à `backend/tests/test_bank_reconciliation_integration.py` :
```python
def _unique_label():
    return f"TestBank-{uuid.uuid4().hex[:8]}"

class TestMappings:
    _cleanup_ids = set()
    _auth = None

    def test_create_mapping(self, auth):
        TestMappings._auth = auth
        payload = {
            "bank_label": _unique_label(),
            "delimiter": ",", "has_header": True,
            "date_column": 0, "date_format": "YYYY-MM-DD",
            "description_column": 1, "amount_mode": "single",
            "amount_column": 2, "sign_convention": "positive_is_credit",
        }
        r = requests.post(f"{BASE_URL}/api/bank/mappings", json=payload, headers=auth)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["id"]
        assert body["bank_label"] == payload["bank_label"]
        TestMappings._cleanup_ids.add(body["id"])

    def test_list_mappings_includes_created(self, auth):
        payload = {
            "bank_label": _unique_label(), "delimiter": ",", "has_header": True,
            "date_column": 0, "date_format": "YYYY-MM-DD",
            "description_column": 1, "amount_mode": "single",
            "amount_column": 2, "sign_convention": "positive_is_credit",
        }
        created = requests.post(f"{BASE_URL}/api/bank/mappings", json=payload, headers=auth).json()
        TestMappings._cleanup_ids.add(created["id"])
        r = requests.get(f"{BASE_URL}/api/bank/mappings", headers=auth)
        assert r.status_code == 200
        ids = [m["id"] for m in r.json()]
        assert created["id"] in ids

    def test_limit_20_mappings(self, auth):
        # crée jusqu'à atteindre 20, puis vérifie 409
        # NB: ce test suppose qu'on part d'un état < 20 — robuste si on cleanup.
        existing = requests.get(f"{BASE_URL}/api/bank/mappings", headers=auth).json()
        to_create = max(0, 20 - len(existing))
        created_now = []
        for _ in range(to_create):
            payload = {
                "bank_label": _unique_label(), "delimiter": ",", "has_header": True,
                "date_column": 0, "date_format": "YYYY-MM-DD",
                "description_column": 1, "amount_mode": "single",
                "amount_column": 2, "sign_convention": "positive_is_credit",
            }
            r = requests.post(f"{BASE_URL}/api/bank/mappings", json=payload, headers=auth)
            assert r.status_code == 201
            created_now.append(r.json()["id"])
            TestMappings._cleanup_ids.add(r.json()["id"])
        # 21ème → 409
        payload = {
            "bank_label": _unique_label(), "delimiter": ",", "has_header": True,
            "date_column": 0, "date_format": "YYYY-MM-DD",
            "description_column": 1, "amount_mode": "single",
            "amount_column": 2, "sign_convention": "positive_is_credit",
        }
        r = requests.post(f"{BASE_URL}/api/bank/mappings", json=payload, headers=auth)
        assert r.status_code == 409
        assert "20" in r.text

    @classmethod
    def teardown_class(cls):
        if not cls._auth:
            return
        # cleanup: les endpoints DELETE mappings n'existent pas en v1.
        # On utilise un cleanup direct mongo en passant par l'API admin ? Non.
        # → on accepte que les mappings s'accumulent dans la DB de test (purgés manuellement).
        pass
```

- [ ] **Step 2: Lancer pour confirmer l'échec**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
# server doit tourner
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_bank_reconciliation_integration.py::TestMappings -v 2>&1 | tail -10
```
Attendu : 404 sur tous (endpoints absents).

- [ ] **Step 3: Implémenter les endpoints**

Ajouter dans `backend/server.py` après les endpoints feature #6 (chercher la dernière route `/api/invoices/.../payments` et insérer après) :

```python
# ─── Bank reconciliation endpoints (feature #7) ───
BANK_MAPPING_LIMIT = 20

@app.get("/api/bank/mappings")
def list_bank_mappings(current_user: User = Depends(get_current_user_with_access)):
    cursor = db.bank_mappings.find({"user_id": current_user.id}, {"_id": 0}).sort("last_used_at", -1)
    return list(cursor)

@app.post("/api/bank/mappings", status_code=201)
def create_bank_mapping(body: dict, current_user: User = Depends(get_current_user_with_access)):
    count = db.bank_mappings.count_documents({"user_id": current_user.id})
    if count >= BANK_MAPPING_LIMIT:
        raise HTTPException(409, f"Limite de {BANK_MAPPING_LIMIT} mappings atteinte")
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "bank_label": (body.get("bank_label") or "").strip()[:60] or "Sans nom",
        "delimiter": body.get("delimiter", ","),
        "has_header": bool(body.get("has_header", True)),
        "date_column": int(body.get("date_column", 0)),
        "date_format": body.get("date_format", "YYYY-MM-DD"),
        "description_column": int(body.get("description_column", 1)),
        "amount_mode": body.get("amount_mode", "single"),
        "amount_column": body.get("amount_column"),
        "debit_column": body.get("debit_column"),
        "credit_column": body.get("credit_column"),
        "sign_convention": body.get("sign_convention", "positive_is_credit"),
        "created_at": now,
        "last_used_at": now,
    }
    db.bank_mappings.insert_one(doc)
    return clean_doc(doc)
```

- [ ] **Step 4: Lancer les tests**

```bash
pytest tests/test_bank_reconciliation_integration.py::TestMappings -v 2>&1 | tail -10
```
Attendu : 3 pass.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_bank_reconciliation_integration.py
git commit -m "feat(bank): GET/POST /api/bank/mappings avec limite 20"
```

---

## Task 4 : Endpoint POST `/api/bank/imports` (dry_run + import complet, sans auto-match)

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_bank_reconciliation_integration.py`

- [ ] **Step 1: Écrire les tests**

Ajouter à `backend/tests/test_bank_reconciliation_integration.py` :
```python
def _csv_bytes(rows, header=True):
    lines = []
    if header:
        lines.append("Date,Description,Montant")
    for r in rows:
        lines.append(",".join(r))
    return ("\n".join(lines) + "\n").encode("utf-8")

def _basic_mapping():
    return {
        "delimiter": ",", "has_header": True,
        "date_column": 0, "date_format": "YYYY-MM-DD",
        "description_column": 1, "amount_mode": "single",
        "amount_column": 2, "sign_convention": "positive_is_credit",
    }

class TestImportDryRun:
    def test_dry_run_returns_parsed_no_write(self, auth):
        csv = _csv_bytes([
            ["2099-03-14", "Costco", "-127.84"],
            ["2099-03-15", "Client Test", "250.00"],
        ])
        files = {"file": ("test.csv", csv, "text/csv")}
        data = {"mapping": __import__("json").dumps(_basic_mapping())}
        r = requests.post(f"{BASE_URL}/api/bank/imports?dry_run=true",
                          files=files, data=data, headers=auth)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "parsed_rows" in body
        assert len(body["parsed_rows"]) == 2
        assert body["parsed_rows"][0]["description"] == "Costco"

class TestImportCreate:
    _cleanup_imports = set()
    _auth = None

    def test_creates_import_and_transactions(self, auth):
        TestImportCreate._auth = auth
        csv = _csv_bytes([
            ["2099-04-14", "Costco", "-127.84"],
            ["2099-04-15", "Salary", "1500.00"],
        ])
        files = {"file": ("test.csv", csv, "text/csv")}
        data = {"mapping": __import__("json").dumps(_basic_mapping()),
                "bank_label": f"DryRunBank-{uuid.uuid4().hex[:6]}"}
        r = requests.post(f"{BASE_URL}/api/bank/imports",
                          files=files, data=data, headers=auth)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["import"]["row_count"] == 2
        assert len(body["transactions"]) == 2
        TestImportCreate._cleanup_imports.add(body["import"]["id"])

    def test_duplicate_csv_returns_409(self, auth):
        csv = _csv_bytes([["2099-05-14", "Unique", "-1.00"]])
        files = {"file": ("dup.csv", csv, "text/csv")}
        data = {"mapping": __import__("json").dumps(_basic_mapping())}
        r1 = requests.post(f"{BASE_URL}/api/bank/imports",
                           files=files, data=data, headers=auth)
        assert r1.status_code == 201
        TestImportCreate._cleanup_imports.add(r1.json()["import"]["id"])
        # re-upload même contenu
        files = {"file": ("dup.csv", csv, "text/csv")}
        data = {"mapping": __import__("json").dumps(_basic_mapping())}
        r2 = requests.post(f"{BASE_URL}/api/bank/imports",
                           files=files, data=data, headers=auth)
        assert r2.status_code == 409
        assert "import_id" in r2.json() or "Duplicate" in r2.text

    def test_oversize_returns_413(self, auth):
        # 5001 lignes → 413
        rows = [[f"2099-06-{(i%28)+1:02d}", f"Row{i}", "1.00"] for i in range(5001)]
        csv = _csv_bytes(rows)
        files = {"file": ("big.csv", csv, "text/csv")}
        data = {"mapping": __import__("json").dumps(_basic_mapping())}
        r = requests.post(f"{BASE_URL}/api/bank/imports",
                          files=files, data=data, headers=auth)
        assert r.status_code == 413

    @classmethod
    def teardown_class(cls):
        if not cls._auth:
            return
        for iid in cls._cleanup_imports:
            try:
                requests.delete(f"{BASE_URL}/api/bank/imports/{iid}?force=true",
                                headers=cls._auth)
            except Exception:
                pass
```

- [ ] **Step 2: Lancer pour confirmer l'échec**

```bash
pytest tests/test_bank_reconciliation_integration.py::TestImportDryRun tests/test_bank_reconciliation_integration.py::TestImportCreate -v 2>&1 | tail -10
```
Attendu : 404.

- [ ] **Step 3: Implémenter l'endpoint POST /api/bank/imports**

Ajouter dans `backend/server.py` (après le POST /mappings) :

```python
import json as _json
from fastapi import UploadFile, File, Form

MAX_BANK_CSV_BYTES = 5 * 1024 * 1024  # 5 MB

@app.post("/api/bank/imports", status_code=201)
async def create_bank_import(
    file: UploadFile = File(...),
    mapping_id: str = Form(None),
    mapping: str = Form(None),
    bank_label: str = Form(None),
    dry_run: bool = False,
    current_user: User = Depends(get_current_user_with_access),
):
    # ── 1. size validation BEFORE hash/parse ──
    raw = await file.read()
    if len(raw) > MAX_BANK_CSV_BYTES:
        raise HTTPException(413, f"File exceeds size limit ({MAX_BANK_CSV_BYTES // (1024*1024)} MB)")

    # ── 2. résoudre mapping ──
    if mapping_id:
        mapping_doc = db.bank_mappings.find_one(
            {"id": mapping_id, "user_id": current_user.id}, {"_id": 0})
        if not mapping_doc:
            raise HTTPException(404, "Mapping not found")
    elif mapping:
        try:
            mapping_doc = _json.loads(mapping)
        except _json.JSONDecodeError:
            raise HTTPException(422, "Invalid mapping JSON")
    else:
        raise HTTPException(422, "mapping_id or mapping required")

    # ── 3. parser (lève ValueError si > ROW_LIMIT) ──
    try:
        parsed = _parse_csv_rows(raw, mapping_doc)
    except ValueError as e:
        if "row limit" in str(e):
            raise HTTPException(413, str(e))
        raise HTTPException(422, str(e))

    # ── 4. dry_run : retourne 10 premières ──
    if dry_run:
        return {"parsed_rows": parsed[:10], "total_rows": len(parsed)}

    # ── 5. file_hash + check duplicate ──
    file_hash = _compute_file_hash(raw)
    existing = db.bank_imports.find_one(
        {"user_id": current_user.id, "file_hash": file_hash}, {"_id": 0})
    if existing:
        raise HTTPException(409, {"detail": "Duplicate import",
                                  "import_id": existing["id"]})

    # ── 6. créer bank_import + bank_transactions ──
    now = datetime.now(timezone.utc).isoformat()
    import_id = str(uuid.uuid4())
    skipped = 0  # _parse_csv_rows skip déjà les lignes vides en interne
    label = (bank_label or mapping_doc.get("bank_label") or "Banque").strip()[:60]
    import_doc = {
        "id": import_id,
        "user_id": current_user.id,
        "mapping_id": mapping_id,
        "bank_label": label,
        "filename": file.filename or "import.csv",
        "file_hash": file_hash,
        "row_count": len(parsed),
        "skipped_rows": skipped,
        "imported_at": now,
        "closed_at": None,
    }
    db.bank_imports.insert_one(import_doc)
    tx_docs = []
    for row in parsed:
        tx = {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            "import_id": import_id,
            "row_index": row["row_index"],
            "date": row["date"],
            "description": row["description"],
            "amount_cad": row["amount_cad"],
            "parse_error": row["parse_error"],
            "raw_line": row.get("raw_line"),
            "status": "unmatched",
            "match_kind": None,
            "match_id": None,
            "invoice_id": None,
            "matched_at": None,
        }
        tx_docs.append(tx)
    if tx_docs:
        db.bank_transactions.insert_many(tx_docs)
    # update mapping last_used_at
    if mapping_id:
        db.bank_mappings.update_one({"id": mapping_id, "user_id": current_user.id},
                                    {"$set": {"last_used_at": now}})
    return {"import": clean_doc(import_doc),
            "transactions": [clean_doc(t) for t in tx_docs]}
```

NB : `UploadFile`, `File`, `Form` doivent déjà être importés depuis fastapi (vérifier `grep "from fastapi" backend/server.py` — sinon ajouter).

- [ ] **Step 4: Lancer les tests**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_bank_reconciliation_integration.py::TestImportDryRun tests/test_bank_reconciliation_integration.py::TestImportCreate -v 2>&1 | tail -15
```
Attendu : 4 pass (1 dry_run + 3 create).

NB : le test `test_oversize_returns_413` va probablement ne PAS exécuter le DELETE de cleanup car l'import n'est jamais créé. Vérifier qu'il pass quand même.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_bank_reconciliation_integration.py
git commit -m "feat(bank): POST /api/bank/imports avec dry_run, anti-duplicate, 5MB cap"
```

---

## Task 5 : Helpers de match `_apply_match`, `_release_bank_transaction`, `_get_invoice_outstanding`

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_bank_reconciliation.py`

- [ ] **Step 1: Tests unitaires (purement Python, sans DB)**

Ajouter à `backend/tests/test_bank_reconciliation.py` :
```python
from server import _get_invoice_outstanding

class TestGetInvoiceOutstanding:
    def test_no_payments(self):
        inv = {"total": 100.0}
        assert _get_invoice_outstanding(inv) == 100.0

    def test_with_payments(self):
        inv = {"total": 100.0, "payments": [{"amount_cad": 30}, {"amount_cad": 20}]}
        assert _get_invoice_outstanding(inv) == 50.0

    def test_overpaid_returns_zero_or_negative(self):
        inv = {"total": 100.0, "payments": [{"amount_cad": 150}]}
        # spec : on retourne max(0, ...) pour l'algo de match
        assert _get_invoice_outstanding(inv) == 0.0
```

- [ ] **Step 2: Implémenter le helper**

Ajouter dans `backend/server.py` après `_parse_csv_rows` :

```python
def _get_invoice_outstanding(invoice):
    """Calcule le solde restant d'une invoice (jamais négatif). Helper pour l'auto-match."""
    payments = invoice.get("payments") or []
    paid = sum(float(p.get("amount_cad", 0) or 0) for p in payments)
    return max(0.0, round(float(invoice.get("total", 0) or 0) - paid, 2))

def _release_bank_transaction(tx_id, user_id):
    """Repasse une bank_transaction en unmatched (used par les cascades)."""
    db.bank_transactions.update_one(
        {"id": tx_id, "user_id": user_id},
        {"$set": {
            "status": "unmatched", "match_kind": None,
            "match_id": None, "invoice_id": None, "matched_at": None,
        }},
    )

def _apply_match(tx, kind, target_id, user_id):
    """Effectue le match entre une bank_transaction et une cible (invoice ou expense).
    Retourne la bank_transaction mise à jour ou lève HTTPException."""
    if tx.get("status") != "unmatched":
        raise HTTPException(409, "Transaction already matched or ignored")
    now = datetime.now(timezone.utc).isoformat()
    tx_amount = abs(float(tx.get("amount_cad", 0) or 0))

    if kind == "invoice_payment":
        invoice = db.invoices.find_one({"id": target_id, "user_id": user_id}, {"_id": 0})
        if not invoice:
            raise HTTPException(404, "Invoice not found")
        if invoice.get("status") == "paid":
            raise HTTPException(409, "Invoice already fully paid")
        payment = {
            "id": str(uuid.uuid4()),
            "amount_cad": round(tx_amount, 2),
            "method": "transfer",
            "date": tx.get("date") or now[:10],
            "reference": (tx.get("description") or "")[:200],
            "bank_transaction_id": tx["id"],
            "created_at": now,
        }
        db.invoices.update_one(
            {"id": target_id, "user_id": user_id},
            {"$push": {"payments": payment}})
        updated = db.invoices.find_one({"id": target_id, "user_id": user_id}, {"_id": 0})
        new_status = _recompute_invoice_status(updated)
        db.invoices.update_one({"id": target_id, "user_id": user_id},
                               {"$set": {"status": new_status}})
        match_kind = "invoice_payment"
        match_id = payment["id"]
        invoice_id = target_id

    elif kind == "expense":
        expense = db.expenses.find_one({"id": target_id, "user_id": user_id}, {"_id": 0})
        if not expense:
            raise HTTPException(404, "Expense not found")
        db.expenses.update_one(
            {"id": target_id, "user_id": user_id},
            {"$set": {"bank_transaction_id": tx["id"]}})
        match_kind = "expense"
        match_id = target_id
        invoice_id = None

    else:
        raise HTTPException(422, "Invalid kind")

    db.bank_transactions.update_one(
        {"id": tx["id"], "user_id": user_id},
        {"$set": {"status": "matched", "match_kind": match_kind,
                  "match_id": match_id, "invoice_id": invoice_id,
                  "matched_at": now}},
    )
    return db.bank_transactions.find_one({"id": tx["id"]}, {"_id": 0})
```

- [ ] **Step 3: Tests pass**

```bash
pytest tests/test_bank_reconciliation.py::TestGetInvoiceOutstanding -v 2>&1 | tail -10
```
Attendu : 3 pass.

- [ ] **Step 4: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_bank_reconciliation.py
git commit -m "feat(bank): helpers _apply_match, _release_bank_transaction, _get_invoice_outstanding"
```

---

## Task 6 : Algorithme d'auto-match `_auto_match_transactions` + intégration POST /imports

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_bank_reconciliation_integration.py`

- [ ] **Step 1: Test d'intégration (match auto réel)**

Ajouter à `backend/tests/test_bank_reconciliation_integration.py` :
```python
def _create_invoice_for_match(auth, total, issue_date, client_name=None):
    """Crée client + invoice statut sent. Retourne (invoice_id, client_id)."""
    cname = client_name or f"Auto-{uuid.uuid4().hex[:6]}"
    c = requests.post(f"{BASE_URL}/api/clients", headers=auth, json={
        "name": cname, "email": f"{cname}@x.test"}).json()
    inv = requests.post(f"{BASE_URL}/api/invoices", headers=auth, json={
        "client_id": c["id"],
        "issue_date": issue_date,
        "due_date": issue_date,
        "items": [{"description": "X", "quantity": 1, "unit_price": total}],
        "province": "AB",  # 5% TPS seulement → total = subtotal × 1.05
        "currency": "CAD",
        "status": "sent",
    }).json()
    return inv["id"], c["id"]

class TestAutoMatch:
    _cleanup = {"imports": set(), "invoices": set(), "clients": set()}
    _auth = None

    def test_credit_matches_existing_invoice(self, auth):
        TestAutoMatch._auth = auth
        # facture totalisant 105 $ (100 + 5% TPS), nom client distinctif
        client_name = f"BANKMATCH{uuid.uuid4().hex[:6].upper()}"
        inv_id, c_id = _create_invoice_for_match(auth, 100, "2099-07-10", client_name)
        TestAutoMatch._cleanup["invoices"].add(inv_id)
        TestAutoMatch._cleanup["clients"].add(c_id)
        # CSV avec un crédit de 105.00 $ le 2099-07-12 (dans la fenêtre ±3j),
        # description contenant le nom du client → score parfait → auto-match
        csv = _csv_bytes([
            ["2099-07-12", f"VIREMENT {client_name} REF12345", "105.00"],
        ])
        files = {"file": ("am.csv", csv, "text/csv")}
        data = {"mapping": __import__("json").dumps(_basic_mapping())}
        r = requests.post(f"{BASE_URL}/api/bank/imports",
                          files=files, data=data, headers=auth)
        assert r.status_code == 201, r.text
        body = r.json()
        TestAutoMatch._cleanup["imports"].add(body["import"]["id"])
        tx = body["transactions"][0]
        assert tx["status"] == "matched"
        assert tx["match_kind"] == "invoice_payment"
        # vérifier que la facture a maintenant un payment
        inv_after = requests.get(f"{BASE_URL}/api/invoices/{inv_id}", headers=auth).json()
        assert len(inv_after["payments"]) == 1
        assert inv_after["status"] == "paid"

    def test_credit_no_match_when_amount_off(self, auth):
        csv = _csv_bytes([
            ["2099-08-10", "Quelque chose", "999999.00"],  # montant improbable
        ])
        files = {"file": ("nm.csv", csv, "text/csv")}
        data = {"mapping": __import__("json").dumps(_basic_mapping())}
        r = requests.post(f"{BASE_URL}/api/bank/imports",
                          files=files, data=data, headers=auth)
        assert r.status_code == 201
        body = r.json()
        TestAutoMatch._cleanup["imports"].add(body["import"]["id"])
        assert body["transactions"][0]["status"] == "unmatched"

    @classmethod
    def teardown_class(cls):
        if not cls._auth:
            return
        for iid in cls._cleanup["imports"]:
            try:
                requests.delete(f"{BASE_URL}/api/bank/imports/{iid}?force=true", headers=cls._auth)
            except: pass
        for invid in cls._cleanup["invoices"]:
            try:
                requests.delete(f"{BASE_URL}/api/invoices/{invid}", headers=cls._auth)
            except: pass
        for cid in cls._cleanup["clients"]:
            try:
                requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth)
            except: pass
```

- [ ] **Step 2: Lancer pour confirmer échec**

```bash
pytest tests/test_bank_reconciliation_integration.py::TestAutoMatch -v 2>&1 | tail -10
```
Attendu : `test_credit_matches_existing_invoice` fail (status reste `unmatched`).

- [ ] **Step 3: Implémenter `_auto_match_transactions` et l'appeler dans POST /imports**

Ajouter dans `backend/server.py` après `_apply_match` :

```python
def _parse_iso_date(s):
    """Tolère 'YYYY-MM-DD', 'YYYY-MM-DDT...' ISO. Retourne datetime.date ou None."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except ValueError:
            return None

def _score_invoice_candidate(tx_date, target, inv, client_name_lower, desc_lower):
    """Score 1-3 pour un candidat invoice. Retourne (score, date_diff_days, amount_diff)."""
    outstanding = _get_invoice_outstanding(inv)
    amount_diff = abs(outstanding - target)
    issue = _parse_iso_date(inv.get("issue_date"))
    due = _parse_iso_date(inv.get("due_date")) or issue
    score = 1  # toujours +1 (filtre amount passé)
    date_diff = None
    if issue:
        d_issue = abs((tx_date - issue).days)
        d_due = abs((tx_date - due).days) if due else d_issue
        date_diff = min(d_issue, d_due)
        if d_issue <= 3 or d_due <= 3:
            score += 1
    if client_name_lower and len(client_name_lower) >= 3 and client_name_lower in desc_lower:
        score += 1
    return score, (date_diff if date_diff is not None else 999), amount_diff

def _score_expense_candidate(tx_date, target, exp, desc_lower):
    amount_diff = abs(float(exp.get("amount_cad", 0)) - target)
    exp_date = _parse_iso_date(exp.get("date"))
    date_diff = abs((tx_date - exp_date).days) if exp_date else 999
    vendor = (exp.get("vendor") or "").lower()
    score = 1
    if date_diff <= 1:
        score += 1
    if vendor and len(vendor) >= 3 and vendor in desc_lower:
        score += 1
    return score, date_diff, amount_diff

def _auto_match_transactions(import_id, user_id):
    """Pour chaque transaction unmatched de l'import, tente un match auto.
    Retourne nombre de matches appliqués."""
    open_invoices = list(db.invoices.find(
        {"user_id": user_id, "status": {"$in": ["sent", "partial", "overdue"]}}, {"_id": 0}))
    open_expenses = list(db.expenses.find(
        {"user_id": user_id, "bank_transaction_id": None}, {"_id": 0}))
    clients_by_id = {c["id"]: (c.get("name") or "")
                     for c in db.clients.find({"user_id": user_id},
                                              {"_id": 0, "id": 1, "name": 1})}

    txs = list(db.bank_transactions.find(
        {"import_id": import_id, "user_id": user_id, "status": "unmatched",
         "parse_error": False}, {"_id": 0}))
    applied = 0
    for tx in txs:
        if tx.get("date") is None or tx.get("amount_cad") is None:
            continue
        tx_date = _parse_iso_date(tx["date"])
        if tx_date is None:
            continue
        target = abs(float(tx["amount_cad"]))
        desc_lower = (tx.get("description") or "").lower()
        candidates = []

        if tx["amount_cad"] > 0:  # crédit → factures
            for inv in open_invoices:
                outstanding = _get_invoice_outstanding(inv)
                if abs(outstanding - target) > 0.01:
                    continue
                issue = _parse_iso_date(inv.get("issue_date"))
                if not issue:
                    continue
                # fenêtre lookback 90j / lookahead 3j sur issue_date
                if not (tx_date - timedelta(days=90) <= issue <= tx_date + timedelta(days=3)):
                    continue
                client_name = clients_by_id.get(inv.get("client_id"), "").lower()
                score, date_diff, amt_diff = _score_invoice_candidate(
                    tx_date, target, inv, client_name, desc_lower)
                candidates.append((score, date_diff, amt_diff,
                                   {"kind": "invoice_payment", "id": inv["id"]}))

        elif tx["amount_cad"] < 0:  # débit → dépenses
            for exp in open_expenses:
                if abs(float(exp.get("amount_cad", 0)) - target) > 0.01:
                    continue
                exp_date = _parse_iso_date(exp.get("date"))
                if not exp_date or abs((tx_date - exp_date).days) > 3:
                    continue
                score, date_diff, amt_diff = _score_expense_candidate(
                    tx_date, target, exp, desc_lower)
                candidates.append((score, date_diff, amt_diff,
                                   {"kind": "expense", "id": exp["id"]}))

        if not candidates:
            continue
        # tri : score desc, date_diff asc, amount_diff asc
        candidates.sort(key=lambda c: (-c[0], c[1], c[2]))
        top = candidates[0]
        # auto-match seulement si UNIQUE candidat score 3 (ou si second a score < 3)
        if top[0] == 3 and (len(candidates) == 1 or candidates[1][0] < 3):
            try:
                _apply_match(tx, top[3]["kind"], top[3]["id"], user_id)
                applied += 1
                # invalider le cache local (expense liée n'est plus disponible)
                if top[3]["kind"] == "expense":
                    open_expenses = [e for e in open_expenses if e["id"] != top[3]["id"]]
                # invoice peut rester (partial) — on la laisse, le solde change
            except HTTPException:
                pass
    return applied
```

Puis modifier la fin de `create_bank_import` pour appeler `_auto_match_transactions` avant le `return` :

```python
    # appeler après db.bank_transactions.insert_many(tx_docs) :
    matched_n = _auto_match_transactions(import_id, current_user.id)
    # re-fetch les transactions pour avoir les statuts à jour
    final_txs = list(db.bank_transactions.find({"import_id": import_id}, {"_id": 0}))
    return {"import": clean_doc(import_doc),
            "transactions": [clean_doc(t) for t in final_txs],
            "auto_matched": matched_n}
```

- [ ] **Step 4: Restart + tests**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_bank_reconciliation_integration.py::TestAutoMatch -v 2>&1 | tail -10
```
Attendu : 2 pass.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_bank_reconciliation_integration.py
git commit -m "feat(bank): algorithme _auto_match_transactions (score 3 = auto, sinon suggestions)"
```

---

## Task 7 : Endpoints GET `/api/bank/imports` (liste + counts live) et GET `/api/bank/imports/{id}` (detail + pagination)

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_bank_reconciliation_integration.py`

- [ ] **Step 1: Tests**

Ajouter à `backend/tests/test_bank_reconciliation_integration.py` :
```python
class TestImportsList:
    _cleanup = set()
    _auth = None

    def test_list_returns_recent_imports_with_counts(self, auth):
        TestImportsList._auth = auth
        csv = _csv_bytes([["2099-09-10", "X", "1.00"]])
        files = {"file": ("a.csv", csv, "text/csv")}
        data = {"mapping": __import__("json").dumps(_basic_mapping())}
        body = requests.post(f"{BASE_URL}/api/bank/imports",
                             files=files, data=data, headers=auth).json()
        TestImportsList._cleanup.add(body["import"]["id"])

        r = requests.get(f"{BASE_URL}/api/bank/imports", headers=auth)
        assert r.status_code == 200
        items = r.json()
        assert len(items) > 0
        # counts live présents
        first = items[0]
        assert "matched_count" in first
        assert "ignored_count" in first
        assert "unmatched_count" in first

    def test_get_detail_returns_transactions(self, auth):
        csv = _csv_bytes([["2099-09-11", "A", "1"], ["2099-09-12", "B", "2"]])
        files = {"file": ("b.csv", csv, "text/csv")}
        data = {"mapping": __import__("json").dumps(_basic_mapping())}
        body = requests.post(f"{BASE_URL}/api/bank/imports",
                             files=files, data=data, headers=auth).json()
        TestImportsList._cleanup.add(body["import"]["id"])

        r = requests.get(f"{BASE_URL}/api/bank/imports/{body['import']['id']}",
                          headers=auth)
        assert r.status_code == 200
        d = r.json()
        assert d["import"]["id"] == body["import"]["id"]
        assert len(d["transactions"]) == 2
        assert d["total_count"] == 2

    def test_get_detail_other_user_returns_404(self, auth):
        r = requests.get(f"{BASE_URL}/api/bank/imports/non-existent-id",
                          headers=auth)
        assert r.status_code == 404

    @classmethod
    def teardown_class(cls):
        if not cls._auth:
            return
        for iid in cls._cleanup:
            try:
                requests.delete(f"{BASE_URL}/api/bank/imports/{iid}?force=true",
                                headers=cls._auth)
            except: pass
```

- [ ] **Step 2: Lancer pour échec**

```bash
pytest tests/test_bank_reconciliation_integration.py::TestImportsList -v 2>&1 | tail -10
```

- [ ] **Step 3: Implémenter les endpoints**

Ajouter dans `backend/server.py` après POST /imports :

```python
def _import_with_live_counts(imp):
    """Enrichit un bank_import avec les counts live des transactions."""
    counts = {"matched": 0, "ignored": 0, "unmatched": 0}
    for s in ("matched", "ignored", "unmatched"):
        counts[s] = db.bank_transactions.count_documents(
            {"import_id": imp["id"], "status": s})
    out = clean_doc(imp)
    out["matched_count"] = counts["matched"]
    out["ignored_count"] = counts["ignored"]
    out["unmatched_count"] = counts["unmatched"]
    return out

@app.get("/api/bank/imports")
def list_bank_imports(limit: int = 50, current_user: User = Depends(get_current_user_with_access)):
    limit = min(max(limit, 1), 50)
    cursor = db.bank_imports.find(
        {"user_id": current_user.id}, {"_id": 0}).sort("imported_at", -1).limit(limit)
    return [_import_with_live_counts(imp) for imp in cursor]

@app.get("/api/bank/imports/{import_id}")
def get_bank_import(import_id: str, page: int = 1, per_page: int = 100,
                    current_user: User = Depends(get_current_user_with_access)):
    per_page = min(max(per_page, 1), 500)
    page = max(page, 1)
    imp = db.bank_imports.find_one({"id": import_id, "user_id": current_user.id}, {"_id": 0})
    if not imp:
        raise HTTPException(404, "Import not found")
    total = db.bank_transactions.count_documents(
        {"import_id": import_id, "user_id": current_user.id})
    cursor = db.bank_transactions.find(
        {"import_id": import_id, "user_id": current_user.id}, {"_id": 0})\
        .sort("row_index", 1).skip((page - 1) * per_page).limit(per_page)
    return {
        "import": _import_with_live_counts(imp),
        "transactions": [clean_doc(t) for t in cursor],
        "total_count": total,
        "page": page,
        "per_page": per_page,
    }
```

- [ ] **Step 4: Tests pass**

```bash
pytest tests/test_bank_reconciliation_integration.py::TestImportsList -v 2>&1 | tail -10
```

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_bank_reconciliation_integration.py
git commit -m "feat(bank): GET /api/bank/imports (list + counts live) et GET /imports/{id}"
```

---

## Task 8 : Endpoints `/api/bank/transactions/{tx_id}/{match,unmatch,ignore,unignore,suggestions}`

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_bank_reconciliation_integration.py`

- [ ] **Step 1: Tests d'intégration**

Ajouter à `backend/tests/test_bank_reconciliation_integration.py` :
```python
class TestMatchEndpoints:
    _cleanup = {"imports": set(), "invoices": set(), "clients": set(), "expenses": set()}
    _auth = None

    def _make_import_with_one_tx(self, auth, amount_cad, date="2099-10-15", desc="X"):
        csv = _csv_bytes([[date, desc, f"{amount_cad:.2f}"]])
        files = {"file": ("m.csv", csv, "text/csv")}
        data = {"mapping": __import__("json").dumps(_basic_mapping())}
        body = requests.post(f"{BASE_URL}/api/bank/imports",
                             files=files, data=data, headers=auth).json()
        TestMatchEndpoints._cleanup["imports"].add(body["import"]["id"])
        return body["transactions"][0]

    def test_match_invoice_creates_payment(self, auth):
        TestMatchEndpoints._auth = auth
        inv_id, c_id = _create_invoice_for_match(auth, 200, "2099-10-15")
        TestMatchEndpoints._cleanup["invoices"].add(inv_id)
        TestMatchEndpoints._cleanup["clients"].add(c_id)
        tx = self._make_import_with_one_tx(auth, 210, "2099-10-15", "NoMatch")
        # tx.amount = 210 mais facture totalise 210 → on évite l'auto-match (description sans nom)
        # on matche manuellement
        r = requests.post(
            f"{BASE_URL}/api/bank/transactions/{tx['id']}/match",
            headers=auth, json={"kind": "invoice_payment", "target_id": inv_id})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "matched"
        # vérifier payment créé
        inv = requests.get(f"{BASE_URL}/api/invoices/{inv_id}", headers=auth).json()
        assert len(inv["payments"]) == 1
        assert inv["status"] == "paid"

    def test_match_paid_invoice_returns_409(self, auth):
        # créer facture déjà paid
        inv_id, c_id = _create_invoice_for_match(auth, 100, "2099-10-20")
        TestMatchEndpoints._cleanup["invoices"].add(inv_id)
        TestMatchEndpoints._cleanup["clients"].add(c_id)
        # ajouter paiement pour passer en paid
        requests.post(f"{BASE_URL}/api/invoices/{inv_id}/payments",
                      headers=auth, json={"amount_cad": 105, "method": "cash"})
        tx = self._make_import_with_one_tx(auth, 105, "2099-10-21", "Tag")
        r = requests.post(
            f"{BASE_URL}/api/bank/transactions/{tx['id']}/match",
            headers=auth, json={"kind": "invoice_payment", "target_id": inv_id})
        assert r.status_code == 409

    def test_match_non_owned_target_returns_404(self, auth):
        tx = self._make_import_with_one_tx(auth, 50, "2099-10-22", "Tag2")
        r = requests.post(
            f"{BASE_URL}/api/bank/transactions/{tx['id']}/match",
            headers=auth, json={"kind": "invoice_payment", "target_id": "bogus-uuid"})
        assert r.status_code == 404

    def test_unmatch_removes_payment(self, auth):
        inv_id, c_id = _create_invoice_for_match(auth, 50, "2099-10-25")
        TestMatchEndpoints._cleanup["invoices"].add(inv_id)
        TestMatchEndpoints._cleanup["clients"].add(c_id)
        tx = self._make_import_with_one_tx(auth, 52.5, "2099-10-25", "TagU")
        requests.post(f"{BASE_URL}/api/bank/transactions/{tx['id']}/match",
                      headers=auth, json={"kind": "invoice_payment", "target_id": inv_id})
        r = requests.post(f"{BASE_URL}/api/bank/transactions/{tx['id']}/unmatch", headers=auth)
        assert r.status_code == 200
        assert r.json()["status"] == "unmatched"
        inv = requests.get(f"{BASE_URL}/api/invoices/{inv_id}", headers=auth).json()
        assert len(inv["payments"]) == 0
        assert inv["status"] in ("sent", "overdue")

    def test_ignore_then_unignore(self, auth):
        tx = self._make_import_with_one_tx(auth, 5, "2099-10-28", "Bank fee")
        r = requests.post(f"{BASE_URL}/api/bank/transactions/{tx['id']}/ignore", headers=auth)
        assert r.json()["status"] == "ignored"
        r = requests.post(f"{BASE_URL}/api/bank/transactions/{tx['id']}/unignore", headers=auth)
        assert r.json()["status"] == "unmatched"

    def test_suggestions_returns_candidates(self, auth):
        # crée 2 factures à 50 $ ; tx de 50 $ → 2 suggestions
        i1, c1 = _create_invoice_for_match(auth, 47.62, "2099-11-01")  # 47.62 * 1.05 ≈ 50
        i2, c2 = _create_invoice_for_match(auth, 47.62, "2099-11-02")
        TestMatchEndpoints._cleanup["invoices"].update([i1, i2])
        TestMatchEndpoints._cleanup["clients"].update([c1, c2])
        tx = self._make_import_with_one_tx(auth, 50.0, "2099-11-03", "ZZZ")
        r = requests.get(f"{BASE_URL}/api/bank/transactions/{tx['id']}/suggestions", headers=auth)
        assert r.status_code == 200
        body = r.json()
        # au moins 1 candidat invoice
        assert isinstance(body.get("invoices"), list)

    @classmethod
    def teardown_class(cls):
        if not cls._auth:
            return
        for iid in cls._cleanup["imports"]:
            try: requests.delete(f"{BASE_URL}/api/bank/imports/{iid}?force=true", headers=cls._auth)
            except: pass
        for invid in cls._cleanup["invoices"]:
            try: requests.delete(f"{BASE_URL}/api/invoices/{invid}", headers=cls._auth)
            except: pass
        for cid in cls._cleanup["clients"]:
            try: requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth)
            except: pass
```

- [ ] **Step 2: Lancer pour échec**

```bash
pytest tests/test_bank_reconciliation_integration.py::TestMatchEndpoints -v 2>&1 | tail -10
```

- [ ] **Step 3: Implémenter les endpoints**

Ajouter dans `backend/server.py` après GET /imports/{id} :

```python
def _get_tx_or_404(tx_id, user_id):
    tx = db.bank_transactions.find_one({"id": tx_id, "user_id": user_id}, {"_id": 0})
    if not tx:
        raise HTTPException(404, "Transaction not found")
    return tx

@app.post("/api/bank/transactions/{tx_id}/match")
def match_bank_transaction(tx_id: str, body: dict,
                            current_user: User = Depends(get_current_user_with_access)):
    tx = _get_tx_or_404(tx_id, current_user.id)
    kind = body.get("kind")
    target_id = body.get("target_id")
    if not target_id:
        raise HTTPException(422, "target_id required")
    return clean_doc(_apply_match(tx, kind, target_id, current_user.id))

@app.post("/api/bank/transactions/{tx_id}/unmatch")
def unmatch_bank_transaction(tx_id: str,
                              current_user: User = Depends(get_current_user_with_access)):
    tx = _get_tx_or_404(tx_id, current_user.id)
    if tx.get("status") != "matched":
        raise HTTPException(409, "Transaction is not matched")
    if tx.get("match_kind") == "invoice_payment":
        invoice = db.invoices.find_one(
            {"id": tx.get("invoice_id"), "user_id": current_user.id}, {"_id": 0})
        if invoice:
            new_payments = [p for p in invoice.get("payments", [])
                            if p.get("id") != tx.get("match_id")]
            db.invoices.update_one(
                {"id": invoice["id"], "user_id": current_user.id},
                {"$set": {"payments": new_payments, "status": "sent"}})
            updated = db.invoices.find_one(
                {"id": invoice["id"], "user_id": current_user.id}, {"_id": 0})
            new_status = _recompute_invoice_status(updated)
            db.invoices.update_one({"id": invoice["id"], "user_id": current_user.id},
                                   {"$set": {"status": new_status}})
    elif tx.get("match_kind") == "expense":
        db.expenses.update_one(
            {"id": tx.get("match_id"), "user_id": current_user.id},
            {"$set": {"bank_transaction_id": None}})
    _release_bank_transaction(tx_id, current_user.id)
    return clean_doc(db.bank_transactions.find_one({"id": tx_id}, {"_id": 0}))

@app.post("/api/bank/transactions/{tx_id}/ignore")
def ignore_bank_transaction(tx_id: str,
                             current_user: User = Depends(get_current_user_with_access)):
    tx = _get_tx_or_404(tx_id, current_user.id)
    if tx.get("status") == "matched":
        raise HTTPException(409, "Cannot ignore a matched transaction; unmatch first")
    db.bank_transactions.update_one(
        {"id": tx_id, "user_id": current_user.id},
        {"$set": {"status": "ignored"}})
    return clean_doc(db.bank_transactions.find_one({"id": tx_id}, {"_id": 0}))

@app.post("/api/bank/transactions/{tx_id}/unignore")
def unignore_bank_transaction(tx_id: str,
                               current_user: User = Depends(get_current_user_with_access)):
    tx = _get_tx_or_404(tx_id, current_user.id)
    if tx.get("status") != "ignored":
        raise HTTPException(409, "Transaction is not ignored")
    db.bank_transactions.update_one(
        {"id": tx_id, "user_id": current_user.id},
        {"$set": {"status": "unmatched"}})
    return clean_doc(db.bank_transactions.find_one({"id": tx_id}, {"_id": 0}))

@app.get("/api/bank/transactions/{tx_id}/suggestions")
def get_bank_suggestions(tx_id: str,
                          current_user: User = Depends(get_current_user_with_access)):
    tx = _get_tx_or_404(tx_id, current_user.id)
    if tx.get("date") is None or tx.get("amount_cad") is None:
        return {"invoices": [], "expenses": []}
    tx_date = _parse_iso_date(tx["date"])
    target = abs(float(tx["amount_cad"]))
    desc_lower = (tx.get("description") or "").lower()
    invoices_out = []
    expenses_out = []
    if tx["amount_cad"] > 0:
        cands = []
        for inv in db.invoices.find(
                {"user_id": current_user.id,
                 "status": {"$in": ["sent", "partial", "overdue"]}}, {"_id": 0}):
            outstanding = _get_invoice_outstanding(inv)
            if abs(outstanding - target) > 0.01:
                continue
            issue = _parse_iso_date(inv.get("issue_date"))
            if not issue or not (tx_date - timedelta(days=90) <= issue <= tx_date + timedelta(days=3)):
                continue
            client = db.clients.find_one(
                {"id": inv.get("client_id"), "user_id": current_user.id},
                {"_id": 0, "name": 1}) or {}
            client_name = (client.get("name") or "").lower()
            score, ddiff, adiff = _score_invoice_candidate(
                tx_date, target, inv, client_name, desc_lower)
            cands.append((score, ddiff, adiff, inv, client.get("name") or ""))
        cands.sort(key=lambda c: (-c[0], c[1], c[2]))
        for score, ddiff, adiff, inv, cname in cands[:3]:
            invoices_out.append({"invoice": clean_doc(inv), "client_name": cname, "score": score})
    elif tx["amount_cad"] < 0:
        cands = []
        for exp in db.expenses.find(
                {"user_id": current_user.id, "bank_transaction_id": None}, {"_id": 0}):
            if abs(float(exp.get("amount_cad", 0)) - target) > 0.01:
                continue
            exp_date = _parse_iso_date(exp.get("date"))
            if not exp_date or abs((tx_date - exp_date).days) > 3:
                continue
            score, ddiff, adiff = _score_expense_candidate(
                tx_date, target, exp, desc_lower)
            cands.append((score, ddiff, adiff, exp))
        cands.sort(key=lambda c: (-c[0], c[1], c[2]))
        for score, ddiff, adiff, exp in cands[:3]:
            expenses_out.append({"expense": clean_doc(exp), "score": score})
    return {"invoices": invoices_out, "expenses": expenses_out}
```

- [ ] **Step 4: Restart + tests**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_bank_reconciliation_integration.py::TestMatchEndpoints -v 2>&1 | tail -15
```
Attendu : 6 pass.

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_bank_reconciliation_integration.py
git commit -m "feat(bank): endpoints /transactions/{tx_id}/{match,unmatch,ignore,unignore,suggestions}"
```

---

## Task 9 : Endpoints `/create-expense` et `/create-invoice` depuis transaction

**Files:**
- Modify: `backend/server.py`
- Test: `backend/tests/test_bank_reconciliation_integration.py`

- [ ] **Step 1: Tests**

Ajouter à `backend/tests/test_bank_reconciliation_integration.py` :
```python
class TestCreateFromTransaction:
    _cleanup = {"imports": set(), "invoices": set(), "clients": set(), "expenses": set()}
    _auth = None

    def _make_tx(self, auth, amount, date="2099-12-15", desc="X"):
        csv = _csv_bytes([[date, desc, f"{amount:.2f}"]])
        files = {"file": ("c.csv", csv, "text/csv")}
        data = {"mapping": __import__("json").dumps(_basic_mapping())}
        body = requests.post(f"{BASE_URL}/api/bank/imports",
                             files=files, data=data, headers=auth).json()
        TestCreateFromTransaction._cleanup["imports"].add(body["import"]["id"])
        return body["transactions"][0]

    def test_create_expense_from_debit(self, auth):
        TestCreateFromTransaction._auth = auth
        tx = self._make_tx(auth, -100.00, "2099-12-10", "Costco fournitures")
        r = requests.post(
            f"{BASE_URL}/api/bank/transactions/{tx['id']}/create-expense",
            headers=auth, json={"category_code": "office_supplies",
                                "vendor": "Costco"})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["expense"]["amount_cad"] == 100.00
        assert body["expense"]["bank_transaction_id"] == tx["id"]
        assert body["transaction"]["status"] == "matched"
        TestCreateFromTransaction._cleanup["expenses"].add(body["expense"]["id"])

    def test_create_invoice_from_credit(self, auth):
        # crée un client
        c = requests.post(f"{BASE_URL}/api/clients", headers=auth, json={
            "name": f"ClientCreate-{uuid.uuid4().hex[:6]}",
            "email": "x@y.test"}).json()
        TestCreateFromTransaction._cleanup["clients"].add(c["id"])
        tx = self._make_tx(auth, 300.00, "2099-12-11", "Encaissement direct")
        r = requests.post(
            f"{BASE_URL}/api/bank/transactions/{tx['id']}/create-invoice",
            headers=auth, json={"client_id": c["id"],
                                "item_description": "Service ad hoc"})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["invoice"]["total"] == 300.00
        assert body["invoice"]["status"] == "paid"
        assert len(body["invoice"]["payments"]) == 1
        assert body["transaction"]["status"] == "matched"
        TestCreateFromTransaction._cleanup["invoices"].add(body["invoice"]["id"])

    @classmethod
    def teardown_class(cls):
        if not cls._auth:
            return
        for iid in cls._cleanup["imports"]:
            try: requests.delete(f"{BASE_URL}/api/bank/imports/{iid}?force=true", headers=cls._auth)
            except: pass
        for eid in cls._cleanup["expenses"]:
            try: requests.delete(f"{BASE_URL}/api/expenses/{eid}", headers=cls._auth)
            except: pass
        for invid in cls._cleanup["invoices"]:
            try: requests.delete(f"{BASE_URL}/api/invoices/{invid}", headers=cls._auth)
            except: pass
        for cid in cls._cleanup["clients"]:
            try: requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth)
            except: pass
```

- [ ] **Step 2: Lancer pour échec**

```bash
pytest tests/test_bank_reconciliation_integration.py::TestCreateFromTransaction -v 2>&1 | tail -10
```

- [ ] **Step 3: Implémenter les endpoints**

Ajouter dans `backend/server.py` après les endpoints /transactions :

```python
@app.post("/api/bank/transactions/{tx_id}/create-expense", status_code=201)
def create_expense_from_tx(tx_id: str, body: dict,
                            current_user: User = Depends(get_current_user_with_access)):
    tx = _get_tx_or_404(tx_id, current_user.id)
    if tx.get("status") != "unmatched":
        raise HTTPException(409, "Transaction already matched or ignored")
    if tx.get("amount_cad") is None or tx.get("date") is None:
        raise HTTPException(422, "Transaction has parse error; cannot create expense")
    category_code = body.get("category_code")
    if not category_code:
        raise HTTPException(422, "category_code required")
    amount = abs(float(tx["amount_cad"]))
    vendor = (body.get("vendor") or tx.get("description") or "")[:60]
    expense_doc = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "date": tx["date"],
        "amount_cad": round(amount, 2),
        "currency": "CAD",
        "exchange_rate_to_cad": 1.0,
        "vendor": vendor,
        "description": (tx.get("description") or "")[:200],
        "bank_transaction_id": tx["id"],
        "tps_paid": 0.0,
        "tvq_paid": 0.0,
        "tvh_paid": 0.0,
        "tps_paid_cad": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # snapshot catégorie ARC (feature #3) si helper disponible
    try:
        snapshot = _build_expense_category_snapshot(category_code, amount)
        expense_doc["category"] = snapshot
    except Exception:
        expense_doc["category"] = {"code": category_code}
    db.expenses.insert_one(expense_doc)
    # appliquer le match
    now = datetime.now(timezone.utc).isoformat()
    db.bank_transactions.update_one(
        {"id": tx_id, "user_id": current_user.id},
        {"$set": {"status": "matched", "match_kind": "expense",
                  "match_id": expense_doc["id"], "matched_at": now}})
    return {"expense": clean_doc(expense_doc),
            "transaction": clean_doc(db.bank_transactions.find_one({"id": tx_id}, {"_id": 0}))}

@app.post("/api/bank/transactions/{tx_id}/create-invoice", status_code=201)
def create_invoice_from_tx(tx_id: str, body: dict,
                            current_user: User = Depends(get_current_user_with_access)):
    tx = _get_tx_or_404(tx_id, current_user.id)
    if tx.get("status") != "unmatched":
        raise HTTPException(409, "Transaction already matched or ignored")
    if tx.get("amount_cad") is None or tx.get("date") is None:
        raise HTTPException(422, "Transaction has parse error")
    if float(tx["amount_cad"]) <= 0:
        raise HTTPException(422, "create-invoice only for positive (credit) transactions")
    client_id = body.get("client_id")
    if not client_id:
        raise HTTPException(422, "client_id required")
    client = db.clients.find_one({"id": client_id, "user_id": current_user.id}, {"_id": 0})
    if not client:
        raise HTTPException(404, "Client not found")
    total = round(abs(float(tx["amount_cad"])), 2)
    item_desc = (body.get("item_description") or
                 f"Encaissement bancaire — {(tx.get('description') or '')[:60]}")
    now = datetime.now(timezone.utc).isoformat()
    count = db.invoices.count_documents({"user_id": current_user.id})
    invoice_doc = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "client_id": client_id,
        "invoice_number": f"INV-{count + 1:04d}",
        "issue_date": tx["date"],
        "due_date": tx["date"],
        "items": [{"description": item_desc, "quantity": 1, "unit_price": total}],
        "subtotal": total,
        "gst_amount": 0.0, "pst_amount": 0.0, "hst_amount": 0.0,
        "total_tax": 0.0, "total": total,
        "province": "AB",  # neutre — pas de taxes ajoutées
        "currency": "CAD", "exchange_rate_to_cad": 1.0, "total_cad": total,
        "status": "paid",
        "notes": "Facture créée depuis rapprochement bancaire — pas de taxes auto. Édite-la si nécessaire.",
        "payments": [{
            "id": str(uuid.uuid4()),
            "amount_cad": total, "method": "transfer",
            "date": tx["date"],
            "reference": (tx.get("description") or "")[:200],
            "bank_transaction_id": tx["id"],
            "created_at": now,
        }],
        "created_at": now,
    }
    invoice_doc["tax_registrations"] = _build_tax_registrations(current_user.id, client_id)
    db.invoices.insert_one(invoice_doc)
    # match
    db.bank_transactions.update_one(
        {"id": tx_id, "user_id": current_user.id},
        {"$set": {"status": "matched", "match_kind": "invoice_payment",
                  "match_id": invoice_doc["payments"][0]["id"],
                  "invoice_id": invoice_doc["id"], "matched_at": now}})
    return {"invoice": clean_doc(invoice_doc),
            "transaction": clean_doc(db.bank_transactions.find_one({"id": tx_id}, {"_id": 0}))}
```

- [ ] **Step 4: Tests**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_bank_reconciliation_integration.py::TestCreateFromTransaction -v 2>&1 | tail -10
```

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_bank_reconciliation_integration.py
git commit -m "feat(bank): POST /create-expense et /create-invoice depuis transaction"
```

---

## Task 10 : Endpoints DELETE et POST `/close` sur imports + cascades

**Files:**
- Modify: `backend/server.py` (ajouter DELETE/close + modifier les 3 DELETE existants pour cascade)
- Test: `backend/tests/test_bank_reconciliation_integration.py`

- [ ] **Step 1: Tests**

```python
class TestCloseAndDelete:
    _cleanup = {"imports": set(), "invoices": set(), "clients": set()}
    _auth = None

    def test_close_import(self, auth):
        TestCloseAndDelete._auth = auth
        csv = _csv_bytes([["2099-11-15", "X", "1"]])
        files = {"file": ("cl.csv", csv, "text/csv")}
        data = {"mapping": __import__("json").dumps(_basic_mapping())}
        imp = requests.post(f"{BASE_URL}/api/bank/imports",
                            files=files, data=data, headers=auth).json()
        TestCloseAndDelete._cleanup["imports"].add(imp["import"]["id"])
        r = requests.post(f"{BASE_URL}/api/bank/imports/{imp['import']['id']}/close",
                          headers=auth)
        assert r.status_code == 204
        # refetch
        d = requests.get(f"{BASE_URL}/api/bank/imports/{imp['import']['id']}",
                          headers=auth).json()
        assert d["import"]["closed_at"] is not None

    def test_delete_open_import_cascade(self, auth):
        inv_id, c_id = _create_invoice_for_match(auth, 100, "2099-11-20")
        TestCloseAndDelete._cleanup["invoices"].add(inv_id)
        TestCloseAndDelete._cleanup["clients"].add(c_id)
        # match via tx
        csv = _csv_bytes([["2099-11-20", "X", "105.00"]])
        files = {"file": ("dc.csv", csv, "text/csv")}
        data = {"mapping": __import__("json").dumps(_basic_mapping())}
        imp = requests.post(f"{BASE_URL}/api/bank/imports",
                            files=files, data=data, headers=auth).json()
        tx_id = imp["transactions"][0]["id"]
        requests.post(f"{BASE_URL}/api/bank/transactions/{tx_id}/match",
                      headers=auth, json={"kind": "invoice_payment", "target_id": inv_id})
        # delete sans force (non fermé) → OK
        r = requests.delete(f"{BASE_URL}/api/bank/imports/{imp['import']['id']}",
                            headers=auth)
        assert r.status_code == 204
        # facture doit avoir perdu son payment
        inv = requests.get(f"{BASE_URL}/api/invoices/{inv_id}", headers=auth).json()
        assert len(inv["payments"]) == 0

    def test_delete_closed_import_needs_force(self, auth):
        csv = _csv_bytes([["2099-11-22", "X", "2"]])
        files = {"file": ("cf.csv", csv, "text/csv")}
        data = {"mapping": __import__("json").dumps(_basic_mapping())}
        imp = requests.post(f"{BASE_URL}/api/bank/imports",
                            files=files, data=data, headers=auth).json()
        requests.post(f"{BASE_URL}/api/bank/imports/{imp['import']['id']}/close",
                      headers=auth)
        r = requests.delete(f"{BASE_URL}/api/bank/imports/{imp['import']['id']}",
                            headers=auth)
        assert r.status_code == 409
        r = requests.delete(
            f"{BASE_URL}/api/bank/imports/{imp['import']['id']}?force=true", headers=auth)
        assert r.status_code == 204

    def test_delete_invoice_releases_bank_tx(self, auth):
        inv_id, c_id = _create_invoice_for_match(auth, 50, "2099-11-25")
        TestCloseAndDelete._cleanup["clients"].add(c_id)
        csv = _csv_bytes([["2099-11-25", "Y", "52.50"]])
        files = {"file": ("dr.csv", csv, "text/csv")}
        data = {"mapping": __import__("json").dumps(_basic_mapping())}
        imp = requests.post(f"{BASE_URL}/api/bank/imports",
                            files=files, data=data, headers=auth).json()
        TestCloseAndDelete._cleanup["imports"].add(imp["import"]["id"])
        tx_id = imp["transactions"][0]["id"]
        requests.post(f"{BASE_URL}/api/bank/transactions/{tx_id}/match",
                      headers=auth, json={"kind": "invoice_payment", "target_id": inv_id})
        # delete facture
        requests.delete(f"{BASE_URL}/api/invoices/{inv_id}", headers=auth)
        # tx repasse unmatched
        d = requests.get(f"{BASE_URL}/api/bank/imports/{imp['import']['id']}",
                          headers=auth).json()
        assert d["transactions"][0]["status"] == "unmatched"

    @classmethod
    def teardown_class(cls):
        if not cls._auth:
            return
        for iid in cls._cleanup["imports"]:
            try: requests.delete(f"{BASE_URL}/api/bank/imports/{iid}?force=true", headers=cls._auth)
            except: pass
        for invid in cls._cleanup["invoices"]:
            try: requests.delete(f"{BASE_URL}/api/invoices/{invid}", headers=cls._auth)
            except: pass
        for cid in cls._cleanup["clients"]:
            try: requests.delete(f"{BASE_URL}/api/clients/{cid}", headers=cls._auth)
            except: pass
```

- [ ] **Step 2: Lancer pour échec**

- [ ] **Step 3: Implémenter close + delete + cascades**

Ajouter les nouveaux endpoints :

```python
from fastapi import Response

@app.post("/api/bank/imports/{import_id}/close")
def close_bank_import(import_id: str,
                       current_user: User = Depends(get_current_user_with_access)):
    res = db.bank_imports.update_one(
        {"id": import_id, "user_id": current_user.id},
        {"$set": {"closed_at": datetime.now(timezone.utc).isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(404, "Import not found")
    return Response(status_code=204)

@app.delete("/api/bank/imports/{import_id}")
def delete_bank_import(import_id: str, force: bool = False,
                       current_user: User = Depends(get_current_user_with_access)):
    imp = db.bank_imports.find_one({"id": import_id, "user_id": current_user.id}, {"_id": 0})
    if not imp:
        raise HTTPException(404, "Import not found")
    if imp.get("closed_at") and not force:
        raise HTTPException(409, "Import is closed; use force=true to confirm")
    # cascade : libérer chaque transaction matchée
    for tx in db.bank_transactions.find(
            {"import_id": import_id, "user_id": current_user.id, "status": "matched"},
            {"_id": 0}):
        if tx.get("match_kind") == "invoice_payment":
            inv = db.invoices.find_one(
                {"id": tx.get("invoice_id"), "user_id": current_user.id}, {"_id": 0})
            if inv:
                new_payments = [p for p in inv.get("payments", [])
                                if p.get("id") != tx.get("match_id")]
                db.invoices.update_one(
                    {"id": inv["id"], "user_id": current_user.id},
                    {"$set": {"payments": new_payments, "status": "sent"}})
                updated = db.invoices.find_one(
                    {"id": inv["id"], "user_id": current_user.id}, {"_id": 0})
                new_status = _recompute_invoice_status(updated)
                db.invoices.update_one({"id": inv["id"], "user_id": current_user.id},
                                       {"$set": {"status": new_status}})
        elif tx.get("match_kind") == "expense":
            db.expenses.update_one(
                {"id": tx.get("match_id"), "user_id": current_user.id},
                {"$set": {"bank_transaction_id": None}})
    db.bank_transactions.delete_many(
        {"import_id": import_id, "user_id": current_user.id})
    db.bank_imports.delete_one({"id": import_id, "user_id": current_user.id})
    return Response(status_code=204)
```

Puis modifier les 3 DELETE existants pour libérer les `bank_transactions`. Chercher dans `backend/server.py` :

**DELETE /api/invoices/{invoice_id}** (autour de ligne 894) :
```python
@app.delete("/api/invoices/{invoice_id}")
def delete_invoice(invoice_id: str, current_user: User = Depends(get_current_user_with_access)):
    inv = db.invoices.find_one({"id": invoice_id, "user_id": current_user.id}, {"_id": 0})
    if inv:
        for payment in inv.get("payments", []) or []:
            btx_id = payment.get("bank_transaction_id")
            if btx_id:
                _release_bank_transaction(btx_id, current_user.id)
    result = db.invoices.delete_one({"id": invoice_id, "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Invoice not found")
    return {"message": "deleted"}
```

**DELETE /api/invoices/{id}/payments/{pid}** (feature #6, autour de ligne 872) — ajouter juste avant le `pull` :
```python
# avant le $pull :
existing_inv = db.invoices.find_one({"id": invoice_id, "user_id": current_user.id}, {"_id": 0})
if existing_inv:
    payment_to_remove = next((p for p in existing_inv.get("payments", [])
                              if p.get("id") == payment_id), None)
    if payment_to_remove and payment_to_remove.get("bank_transaction_id"):
        _release_bank_transaction(payment_to_remove["bank_transaction_id"], current_user.id)
```

**DELETE /api/expenses/{expense_id}** — chercher `def delete_expense` :
```python
@app.delete("/api/expenses/{expense_id}")
def delete_expense(expense_id: str, current_user: User = Depends(get_current_user_with_access)):
    exp = db.expenses.find_one({"id": expense_id, "user_id": current_user.id}, {"_id": 0})
    if exp and exp.get("bank_transaction_id"):
        _release_bank_transaction(exp["bank_transaction_id"], current_user.id)
    result = db.expenses.delete_one({"id": expense_id, "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Expense not found")
    return {"message": "deleted"}
```

- [ ] **Step 4: Tests**

```bash
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_bank_reconciliation_integration.py::TestCloseAndDelete -v 2>&1 | tail -10
# vérifier qu'on ne casse pas les anciens tests
pytest tests/test_partial_payments_integration.py -v 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add backend/server.py backend/tests/test_bank_reconciliation_integration.py
git commit -m "feat(bank): POST /close, DELETE imports avec cascade + cleanup expense/invoice/payment delete"
```

---

## Task 11 : Frontend — `BankReconciliationPage` (liste + entrée sidebar)

**Files:**
- Create: `frontend/src/pages/BankReconciliationPage.js`
- Modify: `frontend/src/App.js` (route + sidebar entry)

- [ ] **Step 1: Identifier le pattern de routing**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
grep -n "currentPage\|setCurrentPage\|sidebar" frontend/src/App.js | head -10
grep -n "import.*Page\|ReportsPage\|InvoicesPage" frontend/src/App.js | head -10
```

Repérer comment ReportsPage est ajouté (entrée sidebar + cas dans le switch).

- [ ] **Step 2: Créer la page**

`frontend/src/pages/BankReconciliationPage.js` :
```jsx
import React, { useState, useEffect } from "react";
import axios from "axios";
import { GitMerge, Plus, FileText } from "lucide-react";
import { BACKEND_URL } from "../config";

export default function BankReconciliationPage() {
  const [imports, setImports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState({ kind: "list" });

  const fetchImports = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${BACKEND_URL}/api/bank/imports`);
      setImports(r.data);
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchImports(); }, []);

  if (view.kind === "wizard") {
    // Placeholder — sera remplacé Task 12
    return <div>Wizard (Task 12)</div>;
  }
  if (view.kind === "matching") {
    return <div>Matching screen for {view.importId} (Task 14)</div>;
  }

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h1 style={{ display: "flex", alignItems: "center", gap: 8, margin: 0 }}>
          <GitMerge size={24} /> Rapprochement bancaire
        </h1>
        <button onClick={() => setView({ kind: "wizard" })}
                style={{ background: "#00A08C", color: "#fff", border: "none",
                         padding: "8px 16px", borderRadius: 8, cursor: "pointer",
                         display: "inline-flex", alignItems: "center", gap: 6 }}>
          <Plus size={16} /> Nouvel import
        </button>
      </div>
      {loading && <p>Chargement…</p>}
      {!loading && imports.length === 0 && (
        <div style={{ textAlign: "center", padding: 60, color: "#6b7280" }}>
          <FileText size={48} style={{ opacity: 0.4 }} />
          <p>Aucun import bancaire pour l'instant.</p>
          <button onClick={() => setView({ kind: "wizard" })}
                  style={{ background: "#00A08C", color: "#fff", border: "none",
                           padding: "10px 20px", borderRadius: 8, cursor: "pointer" }}>
            Importer votre premier relevé
          </button>
        </div>
      )}
      {!loading && imports.length > 0 && (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#f3f4f6" }}>
              <th style={{ textAlign: "left", padding: 10 }}>Date</th>
              <th style={{ textAlign: "left", padding: 10 }}>Banque</th>
              <th style={{ textAlign: "right", padding: 10 }}>Lignes</th>
              <th style={{ textAlign: "right", padding: 10 }}>Rapproché</th>
              <th style={{ textAlign: "right", padding: 10 }}>Progress</th>
              <th style={{ textAlign: "left", padding: 10 }}>État</th>
            </tr>
          </thead>
          <tbody>
            {imports.map((imp) => {
              const total = (imp.row_count || 0) - (imp.skipped_rows || 0);
              const done = (imp.matched_count || 0) + (imp.ignored_count || 0);
              const pct = total > 0 ? Math.round((done / total) * 100) : 0;
              return (
                <tr key={imp.id} style={{ borderBottom: "1px solid #e5e7eb",
                                          cursor: "pointer" }}
                    onClick={() => setView({ kind: "matching", importId: imp.id })}>
                  <td style={{ padding: 10 }}>{(imp.imported_at || "").slice(0, 10)}</td>
                  <td style={{ padding: 10 }}>{imp.bank_label}</td>
                  <td style={{ padding: 10, textAlign: "right" }}>{imp.row_count}</td>
                  <td style={{ padding: 10, textAlign: "right" }}>{done} / {total}</td>
                  <td style={{ padding: 10, textAlign: "right" }}>{pct} %</td>
                  <td style={{ padding: 10 }}>{imp.closed_at ? "Fermé" : "Ouvert"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Ajouter à App.js**

Modifier `frontend/src/App.js` :
- Import : `import BankReconciliationPage from "./pages/BankReconciliationPage";`
- Sidebar : ajouter entrée à côté de Reports (chercher `Rapports` et copier le pattern, label « Rapprochement », key `"bank"`).
- Switch render : `case "bank": return <BankReconciliationPage />;`

- [ ] **Step 4: Sanity parse**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/frontend"
node -e "require('@babel/parser').parse(require('fs').readFileSync('src/pages/BankReconciliationPage.js','utf8'), {sourceType:'module', plugins:['jsx']})"
node -e "require('@babel/parser').parse(require('fs').readFileSync('src/App.js','utf8'), {sourceType:'module', plugins:['jsx']})"
```

- [ ] **Step 5: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/pages/BankReconciliationPage.js frontend/src/App.js
git commit -m "feat(bank): page BankReconciliationPage liste imports + entrée sidebar"
```

---

## Task 12 : Frontend — `BankImportWizard` (étapes 1+2 : upload + mapping)

**Files:**
- Create: `frontend/src/components/BankImportWizard.js`
- Modify: `frontend/src/pages/BankReconciliationPage.js` (remplacer placeholder)

- [ ] **Step 1: Créer le wizard**

`frontend/src/components/BankImportWizard.js` :
```jsx
import React, { useState, useEffect } from "react";
import axios from "axios";
import { Upload, ArrowRight, X } from "lucide-react";
import { BACKEND_URL } from "../config";

const DEFAULT_MAPPING = {
  delimiter: ",", has_header: true,
  date_column: 0, date_format: "YYYY-MM-DD",
  description_column: 1,
  amount_mode: "single", amount_column: 2,
  debit_column: null, credit_column: null,
  sign_convention: "positive_is_credit",
};

export default function BankImportWizard({ onCancel, onDone }) {
  const [step, setStep] = useState(1);
  const [bankLabel, setBankLabel] = useState("");
  const [file, setFile] = useState(null);
  const [mappings, setMappings] = useState([]);
  const [mapping, setMapping] = useState(DEFAULT_MAPPING);
  const [saveMapping, setSaveMapping] = useState(true);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    axios.get(`${BACKEND_URL}/api/bank/mappings`).then(r => setMappings(r.data));
  }, []);

  // Quand bankLabel change, présélectionne un mapping si match
  useEffect(() => {
    const trimmed = bankLabel.trim().toLowerCase();
    const found = mappings.find(m => (m.bank_label || "").trim().toLowerCase() === trimmed);
    if (found) setMapping(found);
  }, [bankLabel, mappings]);

  const onFileChosen = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 5 * 1024 * 1024) {
      setErr("Fichier trop volumineux (max 5 MB)"); return;
    }
    setFile(f); setErr(null);
  };

  const goStep2 = () => {
    if (!file || !bankLabel.trim()) {
      setErr("Banque et fichier requis"); return;
    }
    setStep(2);
  };

  const runPreview = async () => {
    setBusy(true); setErr(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("mapping", JSON.stringify(mapping));
      fd.append("bank_label", bankLabel);
      const r = await axios.post(
        `${BACKEND_URL}/api/bank/imports?dry_run=true`, fd,
        { headers: { "Content-Type": "multipart/form-data" } });
      setPreview(r.data);
    } catch (e) {
      setErr(e.response?.data?.detail || "Erreur de parsing");
    } finally { setBusy(false); }
  };

  const doImport = async () => {
    setBusy(true); setErr(null);
    try {
      // créer le mapping si demandé
      if (saveMapping) {
        try {
          await axios.post(`${BACKEND_URL}/api/bank/mappings`, { ...mapping, bank_label: bankLabel });
        } catch { /* déjà existant, on ignore */ }
      }
      const fd = new FormData();
      fd.append("file", file);
      fd.append("mapping", JSON.stringify(mapping));
      fd.append("bank_label", bankLabel);
      const r = await axios.post(`${BACKEND_URL}/api/bank/imports`, fd,
        { headers: { "Content-Type": "multipart/form-data" } });
      onDone(r.data.import.id);
    } catch (e) {
      if (e.response?.status === 409 && e.response?.data?.import_id) {
        setErr(`Ce CSV a déjà été importé (import ${e.response.data.import_id}).`);
      } else {
        setErr(e.response?.data?.detail || "Erreur d'import");
      }
    } finally { setBusy(false); }
  };

  const setCol = (key) => (e) => setMapping({ ...mapping, [key]: parseInt(e.target.value, 10) });

  return (
    <div style={{ padding: 24, maxWidth: 900, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h2>Nouvel import — Étape {step} / 2</h2>
        <button onClick={onCancel} style={{ background: "none", border: "none", cursor: "pointer" }}>
          <X size={20} />
        </button>
      </div>
      {err && <div style={{ background: "#fee2e2", color: "#991b1b", padding: 10, borderRadius: 6, marginBottom: 12 }}>{err}</div>}

      {step === 1 && (
        <div>
          <label>Banque (ex: « Desjardins perso »)<br />
            <input list="bank-list" value={bankLabel}
                   onChange={(e) => setBankLabel(e.target.value)}
                   style={{ width: "100%", padding: 8, border: "1px solid #d1d5db", borderRadius: 6 }} />
            <datalist id="bank-list">
              {mappings.map(m => <option key={m.id} value={m.bank_label} />)}
            </datalist>
          </label>
          <div style={{ marginTop: 16, padding: 24, border: "2px dashed #d1d5db", borderRadius: 8, textAlign: "center" }}>
            <Upload size={32} style={{ opacity: 0.5 }} />
            <p>Glisser un CSV ou cliquer pour choisir</p>
            <input type="file" accept=".csv,text/csv" onChange={onFileChosen} />
            {file && <p style={{ color: "#059669" }}>{file.name} ({(file.size / 1024).toFixed(1)} Ko)</p>}
          </div>
          <button onClick={goStep2}
                  disabled={!file || !bankLabel.trim()}
                  style={{ marginTop: 16, background: "#00A08C", color: "#fff", border: "none",
                           padding: "10px 20px", borderRadius: 8, cursor: "pointer" }}>
            Suivant <ArrowRight size={14} />
          </button>
        </div>
      )}

      {step === 2 && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 16 }}>
            <label>Délimiteur
              <select value={mapping.delimiter}
                      onChange={(e) => setMapping({ ...mapping, delimiter: e.target.value })}
                      style={{ width: "100%", padding: 6 }}>
                <option value=",">,</option>
                <option value=";">;</option>
                <option value={"\t"}>tab</option>
              </select>
            </label>
            <label>Format date
              <select value={mapping.date_format}
                      onChange={(e) => setMapping({ ...mapping, date_format: e.target.value })}
                      style={{ width: "100%", padding: 6 }}>
                <option>YYYY-MM-DD</option>
                <option>DD/MM/YYYY</option>
                <option>MM/DD/YYYY</option>
              </select>
            </label>
            <label>Première ligne
              <select value={mapping.has_header ? "yes" : "no"}
                      onChange={(e) => setMapping({ ...mapping, has_header: e.target.value === "yes" })}
                      style={{ width: "100%", padding: 6 }}>
                <option value="yes">En-têtes</option>
                <option value="no">Données</option>
              </select>
            </label>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 16 }}>
            <label>Colonne Date (index)
              <input type="number" min="0" value={mapping.date_column} onChange={setCol("date_column")} />
            </label>
            <label>Colonne Description (index)
              <input type="number" min="0" value={mapping.description_column} onChange={setCol("description_column")} />
            </label>
            <label>Mode montant
              <select value={mapping.amount_mode}
                      onChange={(e) => setMapping({ ...mapping, amount_mode: e.target.value })}>
                <option value="single">Une colonne (signe)</option>
                <option value="debit_credit">Débit + Crédit</option>
              </select>
            </label>
            {mapping.amount_mode === "single" ? (
              <label>Colonne Montant
                <input type="number" min="0" value={mapping.amount_column ?? 0}
                       onChange={(e) => setMapping({ ...mapping, amount_column: parseInt(e.target.value, 10) })} />
              </label>
            ) : (
              <div style={{ display: "flex", gap: 10 }}>
                <label>Colonne Débit
                  <input type="number" min="0" value={mapping.debit_column ?? 0}
                         onChange={(e) => setMapping({ ...mapping, debit_column: parseInt(e.target.value, 10) })} />
                </label>
                <label>Colonne Crédit
                  <input type="number" min="0" value={mapping.credit_column ?? 0}
                         onChange={(e) => setMapping({ ...mapping, credit_column: parseInt(e.target.value, 10) })} />
                </label>
              </div>
            )}
          </div>
          <label style={{ display: "block", marginBottom: 12 }}>
            <input type="checkbox" checked={saveMapping}
                   onChange={(e) => setSaveMapping(e.target.checked)} />
            Sauvegarder ce mapping comme « {bankLabel} »
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={runPreview} disabled={busy}
                    style={{ background: "#e5e7eb", padding: "8px 16px", border: "none", borderRadius: 6 }}>
              {busy ? "…" : "Vérifier"}
            </button>
            <button onClick={doImport} disabled={!preview || busy}
                    style={{ background: "#00A08C", color: "#fff", padding: "8px 16px", border: "none", borderRadius: 6 }}>
              Importer
            </button>
            <button onClick={() => setStep(1)} style={{ background: "none", border: "none", color: "#6b7280" }}>
              ← Retour
            </button>
          </div>
          {preview && (
            <div style={{ marginTop: 16 }}>
              <h4>Aperçu ({preview.total_rows} lignes au total) :</h4>
              <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "#f3f4f6" }}>
                    <th style={{ padding: 6, textAlign: "left" }}>Date</th>
                    <th style={{ padding: 6, textAlign: "left" }}>Description</th>
                    <th style={{ padding: 6, textAlign: "right" }}>Montant</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.parsed_rows.map((r, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid #e5e7eb",
                                         color: r.parse_error ? "#dc2626" : "inherit" }}>
                      <td style={{ padding: 6 }}>{r.date || "—"}</td>
                      <td style={{ padding: 6 }}>{r.description}</td>
                      <td style={{ padding: 6, textAlign: "right" }}>{r.amount_cad?.toFixed(2)} $</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Câbler dans BankReconciliationPage**

Dans `BankReconciliationPage.js`, remplacer le placeholder du `view.kind === "wizard"` par :
```jsx
import BankImportWizard from "../components/BankImportWizard";
...
if (view.kind === "wizard") {
  return <BankImportWizard
    onCancel={() => setView({ kind: "list" })}
    onDone={(importId) => { fetchImports(); setView({ kind: "matching", importId }); }}
  />;
}
```

- [ ] **Step 3: Sanity parse**

```bash
node -e "require('@babel/parser').parse(require('fs').readFileSync('frontend/src/components/BankImportWizard.js','utf8'), {sourceType:'module', plugins:['jsx']})"
node -e "require('@babel/parser').parse(require('fs').readFileSync('frontend/src/pages/BankReconciliationPage.js','utf8'), {sourceType:'module', plugins:['jsx']})"
```

- [ ] **Step 4: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/components/BankImportWizard.js frontend/src/pages/BankReconciliationPage.js
git commit -m "feat(bank): BankImportWizard 2 étapes (upload + mapping + dry_run preview)"
```

---

## Task 13 : Frontend — `BankMatchingScreen` (5 états visuels, filtres, progress)

**Files:**
- Create: `frontend/src/components/BankMatchingScreen.js`
- Modify: `frontend/src/pages/BankReconciliationPage.js`

- [ ] **Step 1: Créer le composant**

`frontend/src/components/BankMatchingScreen.js` :
```jsx
import React, { useState, useEffect, useMemo } from "react";
import axios from "axios";
import { Check, X, AlertCircle, Eye, RotateCcw, Trash2, ArrowLeft } from "lucide-react";
import { BACKEND_URL } from "../config";

const fmt = (n) => Number(n || 0).toFixed(2);

export default function BankMatchingScreen({ importId, onBack }) {
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);

  const fetchData = async () => {
    const r = await axios.get(`${BACKEND_URL}/api/bank/imports/${importId}?per_page=500`);
    setData(r.data);
  };
  useEffect(() => { fetchData(); }, [importId]);

  const filteredTxs = useMemo(() => {
    if (!data) return [];
    return data.transactions.filter(t => {
      if (filter === "unmatched" && t.status !== "unmatched") return false;
      if (filter === "matched" && t.status !== "matched") return false;
      if (filter === "ignored" && t.status !== "ignored") return false;
      if (search && !(t.description || "").toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [data, filter, search]);

  if (!data) return <div style={{ padding: 24 }}>Chargement…</div>;

  const imp = data.import;
  const totalActionable = (imp.row_count || 0) - (imp.skipped_rows || 0);
  const done = (imp.matched_count || 0) + (imp.ignored_count || 0);
  const pct = totalActionable > 0 ? Math.round((done / totalActionable) * 100) : 100;

  const onIgnore = async (tx) => {
    setBusy(true);
    try { await axios.post(`${BACKEND_URL}/api/bank/transactions/${tx.id}/ignore`); await fetchData(); }
    finally { setBusy(false); }
  };
  const onUnignore = async (tx) => {
    setBusy(true);
    try { await axios.post(`${BACKEND_URL}/api/bank/transactions/${tx.id}/unignore`); await fetchData(); }
    finally { setBusy(false); }
  };
  const onUnmatch = async (tx) => {
    if (!window.confirm("Défaire ce rapprochement ?")) return;
    setBusy(true);
    try { await axios.post(`${BACKEND_URL}/api/bank/transactions/${tx.id}/unmatch`); await fetchData(); }
    finally { setBusy(false); }
  };
  const onClose = async () => {
    if (!window.confirm("Fermer cet import (lecture seule par la suite) ?")) return;
    await axios.post(`${BACKEND_URL}/api/bank/imports/${importId}/close`);
    onBack();
  };

  return (
    <div style={{ padding: 24 }}>
      <button onClick={onBack} style={{ background: "none", border: "none", cursor: "pointer", color: "#6b7280" }}>
        <ArrowLeft size={14} /> Retour
      </button>
      <h2>{imp.bank_label} — {(imp.imported_at || "").slice(0, 10)}</h2>
      <div style={{ marginBottom: 16 }}>
        <div style={{ height: 8, background: "#e5e7eb", borderRadius: 4, overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${pct}%`, background: pct === 100 ? "#059669" : "#00A08C" }} />
        </div>
        <small>{done} / {totalActionable} ({pct} %)</small>
        {pct === 100 && !imp.closed_at && (
          <button onClick={onClose} style={{ marginLeft: 12, background: "#059669", color: "#fff",
                                              border: "none", padding: "4px 10px", borderRadius: 4, cursor: "pointer" }}>
            Fermer cet import
          </button>
        )}
      </div>
      <div style={{ marginBottom: 16, display: "flex", gap: 8, alignItems: "center" }}>
        {["all", "unmatched", "matched", "ignored"].map(f => (
          <button key={f} onClick={() => setFilter(f)}
                  style={{ background: filter === f ? "#00A08C" : "#e5e7eb",
                           color: filter === f ? "#fff" : "#111",
                           border: "none", padding: "4px 10px", borderRadius: 4, cursor: "pointer" }}>
            {{ all: "Tout", unmatched: "Non rapprochées", matched: "Matchées", ignored: "Ignorées" }[f]}
          </button>
        ))}
        <input placeholder="Recherche…" value={search} onChange={(e) => setSearch(e.target.value)}
               style={{ padding: 6, marginLeft: "auto", border: "1px solid #d1d5db", borderRadius: 4 }} />
      </div>
      <div>
        {filteredTxs.map(tx => (
          <TxRow key={tx.id} tx={tx} busy={busy}
                 onIgnore={() => onIgnore(tx)}
                 onUnignore={() => onUnignore(tx)}
                 onUnmatch={() => onUnmatch(tx)}
                 onRefresh={fetchData} />
        ))}
        {filteredTxs.length === 0 && <p style={{ color: "#6b7280" }}>Aucune transaction.</p>}
      </div>
    </div>
  );
}

function TxRow({ tx, busy, onIgnore, onUnignore, onUnmatch, onRefresh }) {
  const isDebit = tx.amount_cad != null && tx.amount_cad < 0;
  const stateColor = tx.parse_error ? "#dc2626"
    : tx.status === "matched" ? "#059669"
    : tx.status === "ignored" ? "#9ca3af"
    : "#f59e0b";
  return (
    <div style={{ borderLeft: `4px solid ${stateColor}`, background: "#fff",
                  padding: 12, marginBottom: 8, borderRadius: 4,
                  boxShadow: "0 1px 2px rgba(0,0,0,0.05)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ flex: 1 }}>
          <strong>{tx.date || "—"}</strong> — {tx.description}
          {tx.parse_error && <span style={{ color: "#dc2626", marginLeft: 8 }}>(parse error)</span>}
        </div>
        <div style={{ fontWeight: 600, color: isDebit ? "#dc2626" : "#059669", marginRight: 16 }}>
          {tx.amount_cad != null ? fmt(tx.amount_cad) + " $" : "—"}
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          {tx.status === "unmatched" && !tx.parse_error && (
            <>
              <button onClick={onIgnore} disabled={busy} title="Ignorer"
                      style={iconBtn}><X size={14} /></button>
            </>
          )}
          {tx.status === "matched" && (
            <button onClick={onUnmatch} disabled={busy} title="Défaire"
                    style={iconBtn}><RotateCcw size={14} /></button>
          )}
          {tx.status === "ignored" && (
            <button onClick={onUnignore} disabled={busy} title="Restaurer"
                    style={iconBtn}><Check size={14} /></button>
          )}
        </div>
      </div>
    </div>
  );
}

const iconBtn = { background: "#f3f4f6", border: "none", padding: 6, borderRadius: 4, cursor: "pointer" };
```

- [ ] **Step 2: Câbler dans BankReconciliationPage**

Remplacer le placeholder du `view.kind === "matching"` par :
```jsx
import BankMatchingScreen from "../components/BankMatchingScreen";
...
if (view.kind === "matching") {
  return <BankMatchingScreen
    importId={view.importId}
    onBack={() => { fetchImports(); setView({ kind: "list" }); }}
  />;
}
```

- [ ] **Step 3: Sanity parse**

- [ ] **Step 4: Commit**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/components/BankMatchingScreen.js frontend/src/pages/BankReconciliationPage.js
git commit -m "feat(bank): BankMatchingScreen — états visuels, filtres, progression, close"
```

---

## Task 14 : Frontend — Modals « Confirmer suggestion » + « Créer dépense » + « Créer facture » + « Recherche manuelle »

**Files:**
- Create: `frontend/src/components/BankSuggestionsActions.js`
- Create: `frontend/src/components/BankCreateExpenseModal.js`
- Create: `frontend/src/components/BankCreateInvoiceModal.js`
- Create: `frontend/src/components/BankManualSearchModal.js`
- Modify: `frontend/src/components/BankMatchingScreen.js` (utiliser ces modals)

- [ ] **Step 1: Créer `BankSuggestionsActions.js`**

Composant inline qui fetch les suggestions à la demande et affiche les actions :

```jsx
import React, { useState } from "react";
import axios from "axios";
import { BACKEND_URL } from "../config";

export default function BankSuggestionsActions({ tx, onMatched, onIgnore, onOpenManual, onOpenCreate }) {
  const [suggestions, setSuggestions] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${BACKEND_URL}/api/bank/transactions/${tx.id}/suggestions`);
      setSuggestions(r.data);
    } finally { setLoading(false); }
  };

  React.useEffect(() => { if (!tx.parse_error) load(); }, [tx.id]);

  const confirm = async (kind, target_id) => {
    await axios.post(`${BACKEND_URL}/api/bank/transactions/${tx.id}/match`,
      { kind, target_id });
    onMatched();
  };

  if (loading) return <small style={{ color: "#6b7280" }}>Chargement suggestions…</small>;
  const top = suggestions?.invoices?.[0] || suggestions?.expenses?.[0];

  return (
    <div style={{ marginTop: 6, display: "flex", gap: 6, flexWrap: "wrap" }}>
      {top && top.invoice && (
        <>
          <small>Suggestion : {top.invoice.invoice_number} — {top.client_name} ({top.invoice.outstanding_cad || top.invoice.total} $)</small>
          <button onClick={() => confirm("invoice_payment", top.invoice.id)} style={btnGreen}>Confirmer</button>
        </>
      )}
      {top && top.expense && (
        <>
          <small>Suggestion : {top.expense.vendor} ({top.expense.amount_cad} $)</small>
          <button onClick={() => confirm("expense", top.expense.id)} style={btnGreen}>Confirmer</button>
        </>
      )}
      <button onClick={onOpenManual} style={btnGray}>Chercher</button>
      <button onClick={onOpenCreate} style={btnGray}>Créer {tx.amount_cad < 0 ? "dépense" : "facture"}</button>
      <button onClick={onIgnore} style={btnGray}>Ignorer</button>
    </div>
  );
}

const btnGreen = { background: "#059669", color: "#fff", border: "none", padding: "4px 10px", borderRadius: 4, cursor: "pointer", fontSize: 12 };
const btnGray = { background: "#e5e7eb", border: "none", padding: "4px 10px", borderRadius: 4, cursor: "pointer", fontSize: 12 };
```

- [ ] **Step 2: Créer `BankCreateExpenseModal.js`**

```jsx
import React, { useState, useEffect } from "react";
import axios from "axios";
import { X } from "lucide-react";
import { BACKEND_URL } from "../config";

export default function BankCreateExpenseModal({ tx, onClose, onCreated }) {
  const [categories, setCategories] = useState([]);
  const [categoryCode, setCategoryCode] = useState("");
  const [vendor, setVendor] = useState((tx.description || "").slice(0, 60));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    axios.get(`${BACKEND_URL}/api/expense-categories`).then(r => setCategories(r.data));
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!categoryCode) { setErr("Catégorie requise"); return; }
    setBusy(true);
    try {
      await axios.post(`${BACKEND_URL}/api/bank/transactions/${tx.id}/create-expense`,
        { category_code: categoryCode, vendor });
      onCreated();
    } catch (e) {
      setErr(e.response?.data?.detail || "Erreur");
    } finally { setBusy(false); }
  };

  return (
    <div style={overlay} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={modal}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3>Créer une dépense</h3>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer" }}><X size={18} /></button>
        </div>
        <form onSubmit={submit}>
          <div style={{ background: "#f8fafb", padding: 10, borderRadius: 6, marginBottom: 12 }}>
            <small>Depuis ligne CSV :</small><br />
            <strong>{tx.date} — {tx.description}</strong><br />
            <strong>{Math.abs(tx.amount_cad).toFixed(2)} $ CAD</strong>
          </div>
          <label>Vendeur
            <input value={vendor} onChange={(e) => setVendor(e.target.value)}
                   style={{ width: "100%", padding: 6, marginTop: 2 }} />
          </label>
          <label style={{ marginTop: 12, display: "block" }}>Catégorie ARC
            <select value={categoryCode} onChange={(e) => setCategoryCode(e.target.value)}
                    required style={{ width: "100%", padding: 6, marginTop: 2 }}>
              <option value="">— choisir —</option>
              {categories.map(g => (
                <optgroup key={g.group_code} label={g.group_label}>
                  {g.categories.map(c => <option key={c.code} value={c.code}>{c.label}</option>)}
                </optgroup>
              ))}
            </select>
          </label>
          {err && <p style={{ color: "#dc2626" }}>{err}</p>}
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button type="submit" disabled={busy} style={btnGreen}>{busy ? "…" : "Créer"}</button>
            <button type="button" onClick={onClose} style={btnGray}>Annuler</button>
          </div>
        </form>
      </div>
    </div>
  );
}

const overlay = { position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
                  display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 };
const modal = { background: "#fff", borderRadius: 12, padding: 20, width: "90%", maxWidth: 520 };
const btnGreen = { background: "#059669", color: "#fff", border: "none", padding: "8px 16px", borderRadius: 6, cursor: "pointer" };
const btnGray = { background: "#e5e7eb", border: "none", padding: "8px 16px", borderRadius: 6, cursor: "pointer" };
```

- [ ] **Step 3: Créer `BankCreateInvoiceModal.js`**

Structure miroir mais avec sélecteur client (autocomplete sur GET /api/clients) et champ description optionnel. POST `/create-invoice` avec `{client_id, item_description}`.

```jsx
import React, { useState, useEffect } from "react";
import axios from "axios";
import { X } from "lucide-react";
import { BACKEND_URL } from "../config";

export default function BankCreateInvoiceModal({ tx, onClose, onCreated }) {
  const [clients, setClients] = useState([]);
  const [clientId, setClientId] = useState("");
  const [itemDesc, setItemDesc] = useState(`Encaissement bancaire — ${(tx.description || "").slice(0, 60)}`);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    axios.get(`${BACKEND_URL}/api/clients`).then(r => setClients(r.data));
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!clientId) { setErr("Client requis"); return; }
    setBusy(true);
    try {
      await axios.post(`${BACKEND_URL}/api/bank/transactions/${tx.id}/create-invoice`,
        { client_id: clientId, item_description: itemDesc });
      onCreated();
    } catch (e) {
      setErr(e.response?.data?.detail || "Erreur");
    } finally { setBusy(false); }
  };

  return (
    <div style={overlay} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={modal}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3>Créer une facture</h3>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer" }}><X size={18} /></button>
        </div>
        <form onSubmit={submit}>
          <div style={{ background: "#f8fafb", padding: 10, borderRadius: 6, marginBottom: 12 }}>
            <small>Depuis ligne CSV :</small><br />
            <strong>{tx.date} — {tx.description}</strong><br />
            <strong>{Math.abs(tx.amount_cad).toFixed(2)} $ CAD</strong>
          </div>
          <p style={{ background: "#fef3c7", padding: 8, borderRadius: 6, fontSize: 12 }}>
            ⚠ Facture créée sans taxes. Édite-la après si nécessaire.
          </p>
          <label>Client *
            <select value={clientId} onChange={(e) => setClientId(e.target.value)}
                    required style={{ width: "100%", padding: 6, marginTop: 2 }}>
              <option value="">— choisir —</option>
              {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label style={{ marginTop: 12, display: "block" }}>Description de l'article
            <input value={itemDesc} onChange={(e) => setItemDesc(e.target.value)}
                   style={{ width: "100%", padding: 6, marginTop: 2 }} />
          </label>
          {err && <p style={{ color: "#dc2626" }}>{err}</p>}
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button type="submit" disabled={busy} style={btnGreen}>{busy ? "…" : "Créer"}</button>
            <button type="button" onClick={onClose} style={btnGray}>Annuler</button>
          </div>
        </form>
      </div>
    </div>
  );
}

const overlay = { position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
                  display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 };
const modal = { background: "#fff", borderRadius: 12, padding: 20, width: "90%", maxWidth: 520 };
const btnGreen = { background: "#059669", color: "#fff", border: "none", padding: "8px 16px", borderRadius: 6, cursor: "pointer" };
const btnGray = { background: "#e5e7eb", border: "none", padding: "8px 16px", borderRadius: 6, cursor: "pointer" };
```

- [ ] **Step 4: Créer `BankManualSearchModal.js`**

```jsx
import React, { useState, useEffect } from "react";
import axios from "axios";
import { X } from "lucide-react";
import { BACKEND_URL } from "../config";

export default function BankManualSearchModal({ tx, onClose, onMatched }) {
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const isCredit = (tx.amount_cad || 0) > 0;
    (async () => {
      if (isCredit) {
        const invs = (await axios.get(`${BACKEND_URL}/api/invoices`)).data
          .filter(i => ["sent", "partial", "overdue"].includes(i.status));
        setResults(invs.map(i => ({ kind: "invoice_payment", id: i.id,
                                     label: `${i.invoice_number} — Total ${i.total} $ — Solde ${i.outstanding_cad ?? i.total} $` })));
      } else {
        const exps = (await axios.get(`${BACKEND_URL}/api/expenses`)).data
          .filter(e => !e.bank_transaction_id);
        setResults(exps.map(e => ({ kind: "expense", id: e.id,
                                     label: `${e.date} — ${e.vendor || e.description} — ${e.amount_cad} $` })));
      }
    })();
  }, [tx]);

  const match = async (kind, target_id) => {
    setBusy(true);
    try {
      await axios.post(`${BACKEND_URL}/api/bank/transactions/${tx.id}/match`,
        { kind, target_id });
      onMatched();
    } finally { setBusy(false); }
  };

  const [search, setSearch] = useState("");
  const filtered = results.filter(r => r.label.toLowerCase().includes(search.toLowerCase()));

  return (
    <div style={overlay} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={modal}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3>Chercher manuellement</h3>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer" }}><X size={18} /></button>
        </div>
        <input placeholder="Filtrer…" value={search} onChange={(e) => setSearch(e.target.value)}
               style={{ width: "100%", padding: 6, marginBottom: 12 }} />
        <div style={{ maxHeight: 400, overflowY: "auto" }}>
          {filtered.map(r => (
            <div key={r.id} onClick={() => !busy && match(r.kind, r.id)}
                 style={{ padding: 8, borderBottom: "1px solid #e5e7eb", cursor: "pointer" }}
                 onMouseEnter={(e) => e.currentTarget.style.background = "#f3f4f6"}
                 onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
              {r.label}
            </div>
          ))}
          {filtered.length === 0 && <p style={{ color: "#6b7280" }}>Aucun résultat.</p>}
        </div>
      </div>
    </div>
  );
}

const overlay = { position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
                  display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 };
const modal = { background: "#fff", borderRadius: 12, padding: 20, width: "90%", maxWidth: 640 };
```

- [ ] **Step 5: Modifier `BankMatchingScreen` pour appeler ces modals**

Dans `BankMatchingScreen.js`, ajouter state pour les modals ouverts et injecter `<BankSuggestionsActions>` dans le `TxRow` pour les transactions `unmatched` non-parse-error :

```jsx
import BankSuggestionsActions from "./BankSuggestionsActions";
import BankCreateExpenseModal from "./BankCreateExpenseModal";
import BankCreateInvoiceModal from "./BankCreateInvoiceModal";
import BankManualSearchModal from "./BankManualSearchModal";

// dans le composant principal :
const [openManual, setOpenManual] = useState(null);
const [openCreate, setOpenCreate] = useState(null);

// passer onOpenManual / onOpenCreate à TxRow, qui passera à BankSuggestionsActions.

// rendre les modals à la fin du return :
{openManual && (
  <BankManualSearchModal tx={openManual} onClose={() => setOpenManual(null)}
    onMatched={() => { setOpenManual(null); fetchData(); }} />
)}
{openCreate && (openCreate.amount_cad < 0 ? (
  <BankCreateExpenseModal tx={openCreate} onClose={() => setOpenCreate(null)}
    onCreated={() => { setOpenCreate(null); fetchData(); }} />
) : (
  <BankCreateInvoiceModal tx={openCreate} onClose={() => setOpenCreate(null)}
    onCreated={() => { setOpenCreate(null); fetchData(); }} />
))}
```

Et dans `TxRow`, quand `tx.status === "unmatched" && !tx.parse_error`, rendre :
```jsx
<BankSuggestionsActions tx={tx}
  onMatched={onRefresh} onIgnore={onIgnore}
  onOpenManual={() => onOpenManual(tx)}
  onOpenCreate={() => onOpenCreate(tx)} />
```

Adapter les signatures de `TxRow` pour propager `onOpenManual`, `onOpenCreate`.

- [ ] **Step 6: Sanity parse + commit**

```bash
node -e "require('@babel/parser').parse(require('fs').readFileSync('frontend/src/components/BankSuggestionsActions.js','utf8'), {sourceType:'module', plugins:['jsx']})"
node -e "require('@babel/parser').parse(require('fs').readFileSync('frontend/src/components/BankCreateExpenseModal.js','utf8'), {sourceType:'module', plugins:['jsx']})"
node -e "require('@babel/parser').parse(require('fs').readFileSync('frontend/src/components/BankCreateInvoiceModal.js','utf8'), {sourceType:'module', plugins:['jsx']})"
node -e "require('@babel/parser').parse(require('fs').readFileSync('frontend/src/components/BankManualSearchModal.js','utf8'), {sourceType:'module', plugins:['jsx']})"
node -e "require('@babel/parser').parse(require('fs').readFileSync('frontend/src/components/BankMatchingScreen.js','utf8'), {sourceType:'module', plugins:['jsx']})"
```

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add frontend/src/components/BankSuggestionsActions.js frontend/src/components/BankCreateExpenseModal.js frontend/src/components/BankCreateInvoiceModal.js frontend/src/components/BankManualSearchModal.js frontend/src/components/BankMatchingScreen.js
git commit -m "feat(bank): modals suggestions/manual/create-expense/create-invoice câblées dans matching"
```

---

## Task 15 : E2E, push prod, CLAUDE.md

- [ ] **Step 1: Run all backend tests**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro/backend"
source .venv/bin/activate
lsof -ti:8000 | xargs kill 2>/dev/null
nohup uvicorn server:app --port 8000 > /tmp/srv.log 2>&1 &
sleep 5
pytest tests/test_bank_reconciliation.py tests/test_bank_reconciliation_integration.py -v 2>&1 | tail -10
pytest tests/test_partial_payments.py tests/test_partial_payments_integration.py -v 2>&1 | tail -5
pytest tests/test_tax_numbers.py tests/test_tax_registrations_integration.py tests/test_expense_categories.py tests/test_expense_categories_integration.py tests/test_tax_report.py tests/test_tax_report_integration.py tests/test_pnl_report.py tests/test_pnl_report_integration.py -v 2>&1 | tail -5
```

Attendu : ~38 unit + ~30 integration bank-reconciliation + 166 prior = ~234 PASS.

- [ ] **Step 2: Update CLAUDE.md**

Ajouter à la fin de la section « Features livrées » :
```markdown
- **2026-06-17 — Rapprochement bancaire CSV (feature #7)**
  - 3 collections : `bank_mappings` (max 20/user), `bank_imports` (anti-duplicate via sha256+user), `bank_transactions`
  - POST `/api/bank/imports` avec `dry_run=true` (preview) et `dry_run=false` (import complet + auto-match)
  - Algorithme : montant ±0,01 $, date fenêtre 90j lookback / 3j lookahead (factures), ±3j (dépenses) ; score 1-3 ; auto-match seulement si UN candidat score 3
  - Mode `single` ou `debit_credit`, sign_convention, 3 formats date, sanitisation CSV injection
  - Cascade : DELETE invoice/expense/payment libère les `bank_transactions` liées
  - Endpoints /match, /unmatch, /ignore, /unignore, /suggestions, /create-expense, /create-invoice
  - Frontend : page dédiée, wizard 2 étapes, écran de matching avec 5 états visuels + filtres + progression live
  - Limites v1 : CAD seul, max 5 MB / 5 000 lignes, pas de PUT/DELETE mappings (POST seul), pas de OFX, pas de split, pas de mobile responsive
  - Spec : `docs/superpowers/specs/2026-06-17-bank-reconciliation-design.md`
  - Plan : `docs/superpowers/plans/2026-06-17-bank-reconciliation.md`
```

- [ ] **Step 3: Push prod**

```bash
cd "/Users/guillaumedubeau/Documents/Claude code/FacturePro"
git add CLAUDE.md
git commit -m "docs: feature #7 rapprochement bancaire CSV dans changelog"
git push origin main
```

Render + Vercel redéploient automatiquement (~3-5 min total).

- [ ] **Step 4: Smoke test prod (manuel)**

Sur `https://facturepro.ca` :
- Ouvrir Rapprochement
- Importer un petit CSV (3-5 lignes) avec un mapping de test
- Vérifier auto-match sur une facture pré-existante
- Tester ignore/unignore, défaire un match
- Vérifier le compteur live
- Fermer l'import

Si tout OK, feature livrée.

---

## Self-review

**1. Spec coverage** : Tous les éléments majeurs du spec sont couverts :
- ✅ §3 modèle de données (T2-T4)
- ✅ §4 endpoints (T3-T10)
- ✅ §5 auto-match algo (T6)
- ✅ §6 UI flow (T11-T14)
- ✅ §7 edge cases (couverts par tests Task 4/6/8/10)
- ✅ §9 tests (T1-T10 ont leurs tests)
- ✅ §10 observability (logs via FastAPI default — non explicite mais non bloquant en v1)
- ✅ §12 rollout (T15 push prod)

Gaps mineurs acceptés :
- Pas de logs structurés explicites — FastAPI default + print() existants suffisent pour Render debug.
- Pas de test de cellule "=cmd" séparé en intégration — couvert par les tests unitaires sanitize.

**2. Placeholder scan** : Aucun « TBD », « TODO », « implement later ». Tout le code est présent dans les steps.

**3. Type consistency** :
- `match_kind` = `"invoice_payment" | "expense"` partout (DB + API + match algo).
- `bank_transaction.status` = `"unmatched" | "matched" | "ignored"` partout.
- Pas de drift identifié.

Plan prêt à l'exécution.
