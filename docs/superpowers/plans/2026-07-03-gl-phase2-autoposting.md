# Grand livre — Phase 2 : auto-posting (feature #12) — Plan d'implémentation

**Spec source :** `docs/superpowers/specs/2026-07-03-gl-phase2-autoposting-design.md`
**Statut :** prêt à exécuter. Points ouverts §3 du spec tranchés par les recommandations (RECO) : #1 Encaisse (1000) par défaut ; #2 backfill on-demand + dry-run ; #3 auto verrouillées ; #4 GL CAD via `total_cad`/`amount_cad`, revenu/charge par différence. `amount` des dépenses traité **TTC** (RECO §5.6).
**Prérequis :** Grand livre Phase 1 **livré** (`2026-07-03-general-ledger-phase1.md`). Ce plan s'appuie sur ses collections, helpers et endpoints existants sans en migrer le schéma.

---

## REQUIRED SUB-SKILL: subagent-driven-development

**Ce plan s'exécute avec la sub-skill `superpowers:subagent-driven-development`.** L'agent orchestrateur lit ce plan, puis pour CHAQUE tâche ci-dessous :

1. Lance un **subagent d'implémentation** avec le prompt exact de la tâche (bloc « Subagent prompt »). Le subagent suit **`superpowers:test-driven-development`** (RED → GREEN → REFACTOR) : il écrit d'abord le(s) test(s) qui échouent, les fait passer avec le minimum de code, puis nettoie.
2. À la fin de la tâche, lance un **subagent de revue** (`superpowers:requesting-code-review`) qui vérifie : tests écrits AVANT le code, tests verts, critères d'acceptation remplis, aucun placeholder/TODO, périmètre respecté (pas de fuite sur les tâches suivantes).
3. Ne passe à la tâche suivante que lorsque la revue est **APPROVED**. En cas de blocage, applique `superpowers:systematic-debugging`.

**Règles transverses (valables pour toutes les tâches) :**
- **TDD strict.** Aucun code de prod sans test rouge préalable. `cd backend && python -m pytest` doit être vert avant de clore une tâche.
- **Isolation multi-tenant.** Tout accès `journal_entries`/`invoices`/`expenses`/`company_settings` filtre `organization_id` explicitement. Jamais de requête par `source_id` seul. Chaque test crée ses données dans une org dédiée (fixture `org_id`) et vérifie qu'une 2e org ne voit rien.
- **L'auto-posting ne fait JAMAIS échouer l'opération métier** (décision #6). Tout post passe par `_safe_autopost`. Un test le prouve à chaque hook.
- **Purement additif et opt-in.** Aucune donnée métier existante n'est mutée. `autopost_enabled` défaut `False` : tant que `False`, aucun hook ne poste (comportement Phase 1 pur).
- **Montants CAD, équilibre par différence.** La ligne de revenu/charge est calculée par soustraction (`total_cad − Σ taxes_cad`) pour absorber l'arrondi → `_validate_entry_balance` passe toujours.
- **Fichiers :** backend `backend/server.py` ; tests `backend/tests/test_autoposting.py` (unitaires) et `backend/tests/test_autoposting_integration.py` (intégration) ; frontend `frontend/src/...` (LedgerPage). Utiliser des **chemins et numéros de ligne du spec** comme ancres (`server.py:1675`, etc.).
- **Commande de test :** `cd backend && python -m pytest tests/test_autoposting.py tests/test_autoposting_integration.py -q`. Non-régression : `cd backend && python -m pytest -q`.

---

## Contexte de départ (rappel du spec, à ne PAS recoder)

Déjà en place en Phase 1, réutilisé tel quel :

- `_create_journal_entry(...)` (`server.py:1675`) — factory d'écriture ; valide l'équilibre, snapshot les lignes, attribue le n° atomique ; écrit déjà `source_type`/`source_id` **hardcodés `None`** (`server.py:1704`).
- Champs `source_type`/`source_id` sur `journal_entries` + index `(organization_id, source_type, source_id)` (`server.py:1850`).
- `entry_type` accepte déjà `"auto"` à côté de `manual`/`opening`/`reversal`.
- `_account_balance` (`server.py:1605`) compte **toutes** les écritures `posted` sans regarder `reverses_entry_id` → net zéro par construction après contre-passation.
- `reverse_entry` (`server.py:2870`) — primitive de contre-passation miroir POSTED.
- `_ensure_chart_seeded(org_id, user_id)` (`server.py:2483`) — seed lazy du plan comptable.
- `_build_default_accounts` (`server.py:1534`), verrou `_validate_expense_category_code` (`server.py:1443`) — mapping dépense→compte 5xxx par `expense_category_code`.
- Endpoints sources : `PUT /api/invoices/{id}/status` (`3815`), `POST /api/invoices/{id}/payments` (`3822`), `DELETE /api/invoices/{id}/payments/{pid}` (`3847`), `DELETE /api/invoices/{id}` (`3876`), `POST /api/expenses` (`4959`), `PUT /api/expenses/{id}` (`4988`), `DELETE /api/expenses/{id}` (`5037`).
- `_release_bank_transaction(tx_id, scope)` (`server.py:629`) — patron de cascade « défaire l'effet d'un doc supprimé ».
- `_aggregate_pnl(scope, start, end, basis)` (`server.py:322`) — P&L, point de contrôle réconciliation ; conversion CAD ligne `server.py:344`.
- `_current_fiscal_year` (`server.py:2591`) — bornes de l'exercice courant.

---

## Vue d'ensemble des tâches

| # | Tâche | Fichier(s) | Dépend de |
|---|-------|-----------|-----------|
| 1 | Threader `source_type`/`source_id` dans `_create_journal_entry` | server.py | — |
| 2 | Migration idempotente : champs `company_settings` + index unique partiel | server.py | 1 |
| 3 | Primitives `_find_live_source_entry` / `_post_source_entry` / `_unpost_source_entry` | server.py | 1,2 |
| 4 | Garde-fou `_safe_autopost` + résolution de comptes `_resolve_ledger_account` | server.py | 3 |
| 5 | Mapping facture→revenu `_build_invoice_revenue_lines` + `_autopost_invoice_revenue` | server.py | 4 |
| 6 | Mapping paiement→encaissement + mapping dépense→charge | server.py | 4 |
| 7 | Hook `PUT /invoices/{id}/status` (table de transitions) | server.py | 5 |
| 8 | Hooks paiements : POST + DELETE payment | server.py | 6 |
| 9 | Hooks facture supprimée (cascade) + dépenses POST/PUT/DELETE | server.py | 6,8 |
| 10 | Verrou endpoints manuels (`entry_type=="auto"` → 400) | server.py | 3 |
| 11 | Endpoints `/api/ledger/autopost/status` + `repair` | server.py | 4 |
| 12 | Endpoint backfill (dry-run + apply, idempotent) | server.py | 5,6 |
| 13 | Endpoint réconciliation P&L `/api/ledger/reconciliation` | server.py | 5,6 |
| 14 | Tests intégration bout-en-bout (cycles, isolation, non-régression) | tests | 7-13 |
| 15 | Frontend : onglet Auto-posting + badges + indicateurs d'erreur | frontend | 11,12,13 |
| 16 | Push + mise à jour CLAUDE.md | — | 1-15 |

---

## Tâche 1 — Threader `source_type`/`source_id` dans `_create_journal_entry`

**Objectif :** rendre la factory Phase 1 capable de lier une écriture à un document source, sans changer la structure du document (rétrocompatible, défauts `None`).

**Subagent prompt :**
> Suis `superpowers:test-driven-development`.
>
> **RED.** Dans `backend/tests/test_autoposting.py` (nouveau fichier), écris un test unitaire `test_create_journal_entry_threads_source` qui appelle `_create_journal_entry(org_id, user_id, entry_date="2026-07-01", description="x", lines=[<Dr 1000 100 / Cr 4000 100>], status="posted", entry_type="auto", source_type="invoice", source_id="inv-1")` et vérifie que le document inséré dans `journal_entries` porte `source_type == "invoice"` et `source_id == "inv-1"`. Écris aussi `test_create_journal_entry_source_defaults_none` : sans passer les params, le doc a `source_type is None` et `source_id is None` (non-régression Phase 1). Utilise la fixture d'org/DB de test existante (regarde `backend/tests/` pour le pattern de fixture Mongo et de seed du plan comptable).
>
> **GREEN.** Dans `backend/server.py`, modifie la signature de `_create_journal_entry` (`server.py:1675`) pour ajouter `source_type: Optional[str] = None, source_id: Optional[str] = None`. Remplace l'écriture hardcodée `None` (`server.py:1704`) par ces paramètres. C'est le **seul** changement de la Phase 1.
>
> **REFACTOR.** Vérifie qu'aucun appelant existant n'est cassé (`cd backend && python -m pytest -q`).

**Critères d'acceptation :**
- Signature : `..., source_type: Optional[str] = None, source_id: Optional[str] = None` ; le doc écrit ces valeurs.
- Sans params → `None`/`None` (comportement manuel Phase 1 inchangé).
- `cd backend && python -m pytest tests/test_autoposting.py -q` vert ; suite Phase 1 non régressée.

---

## Tâche 2 — Migration idempotente : champs `company_settings` + index unique partiel

**Objectif :** ajouter les flags org (`autopost_enabled`, `expense_default_credit_account`) par `setdefault` et durcir l'idempotence via un index unique partiel sur les écritures auto vivantes.

**Subagent prompt :**
> Suis `superpowers:test-driven-development`.
>
> **RED.** Dans `test_autoposting.py`, écris `test_migration_seeds_autopost_settings` : après exécution de `migrate_general_ledger_autopost_v1(db)` sur une org dont `company_settings` n'a pas les champs, le doc gagne `autopost_enabled == False` et `expense_default_credit_account == "1000"` ; une org qui a déjà `autopost_enabled == True` n'est PAS écrasée (idempotence — `setdefault`, pas `set`). Écris `test_autopost_unique_partial_index` : insère deux écritures `entry_type="auto"`, `reverses_entry_id=None`, mêmes `(organization_id, source_type, source_id)` → la 2e lève `pymongo.errors.DuplicateKeyError` ; mais un miroir `entry_type="reversal"` avec les mêmes clés est accepté (hors du filtre partiel).
>
> **GREEN.** Dans `server.py`, écris `migrate_general_ledger_autopost_v1(db)` qui, pour chaque `company_settings`, applique `update_many({}, {"$setdefault"...})` — Mongo n'a pas `$setdefault`, donc fais deux `update_many` ciblés `{"autopost_enabled": {"$exists": False}}` → `{"$set": {"autopost_enabled": False}}` et idem pour `expense_default_credit_account` → `"1000"`. Crée l'index :
> ```python
> db.journal_entries.create_index(
>     [("organization_id", 1), ("source_type", 1), ("source_id", 1)],
>     unique=True,
>     partialFilterExpression={"entry_type": "auto", "reverses_entry_id": None},
>     name="uniq_live_auto_source",
> )
> ```
> Appelle `migrate_general_ledger_autopost_v1` au démarrage, à côté des autres migrations GL Phase 1 (cherche l'endroit où la migration Phase 1 est invoquée au boot et ajoute l'appel juste après). Rends la création d'index tolérante à un index déjà présent (try/except `OperationFailure` sur conflit de nom, log warning).
>
> **REFACTOR.** Relance la migration deux fois dans un test → aucun effet la 2e fois.

**Critères d'acceptation :**
- Champs posés uniquement s'ils manquent ; valeurs pré-existantes préservées.
- Index `uniq_live_auto_source` créé avec le `partialFilterExpression` exact ci-dessus.
- Migration rejouable sans erreur ; appelée au boot après la migration Phase 1.

---

## Tâche 3 — Primitives `_find_live_source_entry` / `_post_source_entry` / `_unpost_source_entry`

**Objectif :** la couche idempotente partagée (§6.1 du spec). Un doc source = une écriture auto vivante ; régénération = contre-passer + reposter.

**Subagent prompt :**
> Suis `superpowers:test-driven-development`.
>
> **RED.** Dans `test_autoposting.py` :
> - `test_find_live_ignores_reversed` : pose une écriture auto puis contre-passe-la (via `_unpost_source_entry`) ; `_find_live_source_entry` retourne `None`. Après un nouveau `_post_source_entry`, il retourne l'unique post vivant.
> - `test_post_source_entry_idempotent` : appelle `_post_source_entry(...)` deux fois avec les mêmes `(source_type, source_id)` → 1 seule écriture en base ; le 2e appel retourne `None` (no-op).
> - `test_unpost_creates_mirror_net_zero` : pose Dr 1000 100 / Cr 4000 100, contre-passe ; vérifie qu'un miroir `entry_type="reversal"`, `reverses_entry_id == live["id"]`, `source_type`/`source_id` conservés est créé ; que `live` gagne `reversed_by_entry_id` ; et que `_account_balance` de 1000 et 4000 revient à 0.
> - `test_unpost_noop_when_nothing` : `_unpost_source_entry` sur un source inexistant retourne `None` sans lever.
> - `test_unpost_no_double_mirror` : contre-passer deux fois de suite → un seul miroir (2e appel no-op car déjà `reversed_by_entry_id`).
>
> **GREEN.** Dans `server.py`, implémente exactement (adapte les noms de collection `db.journal_entries` à ceux du code) :
> ```python
> def _find_live_source_entry(org_id, source_type, source_id):
>     return db.journal_entries.find_one({
>         "organization_id": org_id, "source_type": source_type,
>         "source_id": source_id, "entry_type": "auto",
>         "reversed_by_entry_id": None,
>     }, {"_id": 0})
>
> def _post_source_entry(org_id, user_id, source_type, source_id, entry_date,
>                        description, lines, reference=None):
>     if _find_live_source_entry(org_id, source_type, source_id):
>         return None
>     return _create_journal_entry(
>         org_id, user_id, entry_date=entry_date, description=description,
>         lines=lines, status="posted", entry_type="auto", reference=reference,
>         source_type=source_type, source_id=source_id)
>
> def _unpost_source_entry(org_id, user_id, source_type, source_id, rev_date=None):
>     live = _find_live_source_entry(org_id, source_type, source_id)
>     if not live:
>         return None
>     # Réutilise la primitive interne de contre-passation de reverse_entry (server.py:2870) :
>     # crée le miroir via _create_journal_entry(entry_type="reversal",
>     # reverses_entry_id=live["id"], lines = miroir Dr<->Cr des lignes de `live`,
>     # entry_date = rev_date or live["entry_date"], source_type/source_id conservés,
>     # status="posted"), puis pose reversed_by_entry_id sur `live`.
>     return <miroir>
> ```
> Pour `_unpost_source_entry`, **factorise avec `reverse_entry`** : extrais la logique de miroir de `reverse_entry` (`server.py:2870`) dans un helper interne `_reverse_entry_internal(org_id, user_id, entry, rev_date, source_type=None, source_id=None)` que les deux appellent, de sorte que la contre-passation auto emprunte EXACTEMENT le même chemin que la manuelle (pas de mécanisme parallèle).
>
> **REFACTOR.** Vérifie que `reverse_entry` (manuel) fonctionne toujours après extraction du helper (relance les tests Phase 1 de contre-passation).

**Critères d'acceptation :**
- `_find_live_source_entry` ne retourne QUE le post `auto` non contre-passé, filtré par org.
- `_post_source_entry` no-op si un vivant existe (retourne `None`).
- `_unpost_source_entry` crée un miroir via le même chemin que `reverse_entry`, pose `reversed_by_entry_id`, net zéro, no-op si rien/déjà contre-passé.
- Tests Phase 1 de contre-passation manuelle toujours verts.

---

## Tâche 4 — `_safe_autopost` + `_resolve_ledger_account`

**Objectif :** le garde-fou robustesse (décision #6) et la résolution de compte par numéro canonique (seed lazy déclenché).

**Subagent prompt :**
> Suis `superpowers:test-driven-development`.
>
> **RED.** Dans `test_autoposting.py` :
> - `test_safe_autopost_swallows_and_records` : `_safe_autopost(lambda: (_ for _ in ()).throw(RuntimeError("boom")), "invoices", inv_id, {"organization_id": org_id})` ne lève PAS ; le doc `invoices` gagne un `autopost_error` (string horodatée, générique, **sans** `str(e)` — le message ne doit pas contenir "boom").
> - `test_safe_autopost_clears_on_success` : un doc avec `autopost_error` posé ; `_safe_autopost(fn_ok, ...)` exécute `fn_ok` et `$unset` le champ.
> - `test_resolve_ledger_account_seeds_and_finds` : sur une org qui n'a JAMAIS ouvert le GL, `_resolve_ledger_account(org_id, user_id, "4000")` déclenche `_ensure_chart_seeded` puis retourne le compte 4000. `test_resolve_ledger_account_creates_on_the_fly` : `_resolve_ledger_account(org_id, user_id, "2120", create_if_missing=True, kind="liability", name="TVH à payer")` crée 2120 (idempotent : 2e appel ne duplique pas). `_resolve_ledger_account(org_id, user_id, "9999")` (absent, sans create) retourne `None`.
>
> **GREEN.** Dans `server.py` :
> ```python
> def _safe_autopost(fn, source_doc_collection, source_doc_id, org_scope):
>     try:
>         fn()
>         db[source_doc_collection].update_one(
>             {"id": source_doc_id, **org_scope}, {"$unset": {"autopost_error": ""}})
>     except Exception as e:
>         logger.warning("autopost failed for %s: %s", source_doc_id, type(e).__name__)
>         db[source_doc_collection].update_one(
>             {"id": source_doc_id, **org_scope},
>             {"$set": {"autopost_error": f"{datetime.now(timezone.utc).isoformat()} — échec auto-posting"}})
> ```
> `_resolve_ledger_account(org_id, user_id, number, create_if_missing=False, kind=None, name=None)` : appelle `_ensure_chart_seeded(org_id, user_id)` ; `find_one({"organization_id": org_id, "account_number": number, ...})` (adapte le nom du champ n° de compte au schéma Phase 1) ; si absent et `create_if_missing`, crée le compte système (idempotent, re-`find_one` après création pour absorber une race) ; sinon retourne `None`. Adapte `db[source_doc_collection]` si le code accède aux collections par variable nommée plutôt que par index.
>
> **REFACTOR.** Confirme que `_resolve_ledger_account` sur un plan déjà seedé n'appelle pas de re-seed coûteux (idempotence de `_ensure_chart_seeded`).

**Critères d'acceptation :**
- `_safe_autopost` ne propage jamais ; pose un `autopost_error` générique horodaté (pas de `str(e)`) ; efface au succès.
- `_resolve_ledger_account` seed lazy, retourne le compte ou `None` ; crée à la volée (idempotent) si demandé.

---

## Tâche 5 — Mapping facture→revenu + `_autopost_invoice_revenue`

**Objectif :** construire l'écriture de revenu accrual, conversion CAD, revenu par différence, équilibre garanti (§5.1). Comptes de taxe ON créés à la volée.

**Subagent prompt :**
> Suis `superpowers:test-driven-development`.
>
> **RED.** Dans `test_autoposting.py`, teste `_build_invoice_revenue_lines(inv)` puis `_autopost_invoice_revenue(org_id, user_id, inv)` :
> - QC CAD : facture total_cad 115, gst 5, pst 9.975 (tvq), hst 0 → lignes Dr 1100=115 / Cr 4000=100.025 (par différence) / Cr 2100=5 / Cr 2110=9.975. Écriture équilibrée.
> - ON : hst_amount>0 → crédite 2120 (**créé à la volée** si absent), pas de 2100/2110.
> - USD : `currency="USD"`, `exchange_rate_to_cad=1.35`, taxes en USD ; les taxes sont divisées par le taux (`_cad`), `ar_cad = total_cad` inchangé, `revenue_cad = ar_cad − Σ taxes_cad` → écriture équilibrée au cent près.
> - Sans taxes : 2 lignes Dr 1100 / Cr 4000.
> - Métadonnées : `source_type="invoice"`, `source_id=inv["id"]`, `entry_date=inv["issue_date"][:10]`, `description=f"Facture {inv['invoice_number']}"`, `reference=inv["invoice_number"]`.
> - Idempotence : `_autopost_invoice_revenue` deux fois → 1 écriture.
>
> **GREEN.** Dans `server.py` :
> ```python
> def _build_invoice_revenue_lines(org_id, user_id, inv):
>     rate = inv.get("exchange_rate_to_cad") or 1.0
>     def _cad(x):
>         x = x or 0
>         return round((x / rate), 2) if inv.get("currency") != "CAD" and rate > 0 else round(x, 2)
>     gst_cad = _cad(inv.get("gst_amount"))
>     qst_cad = _cad(inv.get("pst_amount"))
>     hst_cad = _cad(inv.get("hst_amount"))
>     ar_cad = round(inv["total_cad"], 2)
>     revenue_cad = round(ar_cad - gst_cad - qst_cad - hst_cad, 2)
>     lines = [debit(1100, ar_cad), credit(4000, revenue_cad)]
>     if gst_cad > 0: lines.append(credit(2100, gst_cad))
>     if qst_cad > 0: lines.append(credit(2110, qst_cad))
>     if hst_cad > 0:
>         _resolve_ledger_account(org_id, user_id, "2120", create_if_missing=True,
>                                 kind="liability", name="TVH à payer")
>         lines.append(credit(2120, hst_cad))
>     return lines
> ```
> Où `debit(n, amt)`/`credit(n, amt)` résolvent l'`account_id` via `_resolve_ledger_account` et produisent une ligne au format attendu par `_create_journal_entry` (regarde le format de ligne exact d'une écriture manuelle Phase 1). `_autopost_invoice_revenue` appelle `_build_invoice_revenue_lines` puis `_post_source_entry("invoice", inv["id"], entry_date=inv["issue_date"][:10], description=f"Facture {inv['invoice_number']}", lines=..., reference=inv["invoice_number"])`.
>
> **REFACTOR.** Extrais les helpers `debit`/`credit` s'ils seront réutilisés en Tâche 6.

**Critères d'acceptation :**
- Écriture toujours équilibrée (revenu par différence), y compris USD.
- 2120/1220 créés à la volée quand la taxe correspondante > 0.
- Métadonnées exactes ; idempotent.

---

## Tâche 6 — Mapping paiement→encaissement + mapping dépense→charge

**Objectif :** les deux autres mappings (§5.2, §5.6). `amount` dépense traité TTC (charge nette par différence) ; crédit selon `expense_default_credit_account`.

**Subagent prompt :**
> Suis `superpowers:test-driven-development`.
>
> **RED.** Dans `test_autoposting.py` :
> - **Paiement** — `_autopost_payment(org_id, user_id, inv, payment)` : Dr 1000 = `payment["amount_cad"]` / Cr 1100 = `payment["amount_cad"]`. `source_type="invoice_payment"`, `source_id=payment["id"]`, `entry_date=payment["date"]`, `description=f"Paiement facture {inv['invoice_number']}"`, `reference=payment.get("reference")`. Idempotent.
> - **Dépense** — `_autopost_expense(org_id, user_id, expense)` : compte 5xxx résolu via `_resolve_expense_account(org_id, expense["category_code"])` ; **fallback 5900** si non mappé ; `expense_net_cad = amount_cad − gst_paid_cad − qst_paid_cad − hst_paid_cad` (charge par différence) ; taxes récupérables en Dr 1200/1210/1220 (1220 créé à la volée si hst>0) ; crédit = `amount_cad` sur 1000 (défaut) **ou** 2000 selon `company_settings.expense_default_credit_account`. Cas : QC avec taxes ; sans taxe (2 lignes) ; catégorie non mappée → 5900 ; flag A/P → crédit 2000. `source_type="expense"`, `source_id=expense["id"]`, `entry_date=expense["expense_date"][:10]`, `description=expense.get("description") or expense.get("category")`, `reference=None`. Écriture toujours équilibrée.
>
> **GREEN.** Dans `server.py`, implémente `_autopost_payment` et `_autopost_expense` + `_resolve_expense_account(org_id, category_code)` (find compte 5xxx où `expense_category_code == category_code`, sinon 5900). Le crédit dépense lit `company_settings.expense_default_credit_account` (défaut `"1000"`, valider ∈ {"1000","2000"}). Réutilise `debit`/`credit`/`_post_source_entry`.
>
> **REFACTOR.** Vérifie l'équilibre par différence dans tous les cas de taxe.

**Critères d'acceptation :**
- Paiement : Dr 1000 / Cr 1100 = amount_cad ; métadonnées exactes ; idempotent.
- Dépense : 5xxx (fallback 5900), taxes en 12xx, charge nette par différence, crédit 1000/2000 selon flag ; équilibré ; idempotent.

---

## Tâche 7 — Hook `PUT /api/invoices/{id}/status` (table de transitions)

**Objectif :** brancher l'auto-posting sur le changement de statut, avec lecture de l'ancien statut avant l'update et respect de la table de vérité §5.5.

**Subagent prompt :**
> Suis `superpowers:test-driven-development`.
>
> **RED.** Dans `test_autoposting_integration.py` (nouveau), via le client HTTP de test et une org avec `autopost_enabled=True` :
> - `draft → sent` : revenu posté (1 écriture auto `4000`), balance équilibrée.
> - `sent → overdue` : aucune nouvelle écriture (accrual, no-op).
> - `sent → draft` : revenu contre-passé, net zéro sur 1100/4000, 1 seul vivant = None.
> - `draft → sent → draft → sent` : 1 seul post vivant à la fin (les anciens contre-passés).
> - `autopost_enabled=False` : `draft → sent` ne crée AUCUNE écriture.
>
> **GREEN.** Dans `server.py`, `update_invoice_status` (`server.py:3815`) : **lire l'ancien statut** (`find_one` avant l'`update_one`). Après l'update, garder par `if company_settings.autopost_enabled`. Écris `_autopost_invoice_status_transition(org_id, user_id, old_status, new_status, inv)` :
> ```python
> non_draft = {"sent", "partial", "paid", "overdue"}
> if old_status == "draft" and new_status in non_draft:
>     _autopost_invoice_revenue(org_id, user_id, inv)          # poste (idempotent)
> elif old_status in non_draft and new_status == "draft":
>     _unpost_source_entry(org_id, user_id, "invoice", inv["id"])  # contre-passe
> # tout autre cas (sent↔overdue, →paid) : rien
> ```
> Enveloppe l'appel dans `_safe_autopost(...)` avec `_ensure_chart_seeded` en amont. **Ne pas** re-poster le revenu sur les transitions `partial`/`paid` issues de `_recompute_invoice_status` (le paiement est géré en Tâche 8).
>
> **REFACTOR.** Confirme que l'ancien comportement (update_one nu) reste correct côté métier.

**Critères d'acceptation :**
- Ancien statut lu avant update ; table §5.5 respectée exactement.
- `autopost_enabled=False` → aucun post.
- Échec d'auto-posting ne fait pas échouer le `PUT` (200).

---

## Tâche 8 — Hooks paiements (POST + DELETE payment)

**Objectif :** encaissement à l'ajout, contre-passation à la suppression (§5.2, §5.3).

**Subagent prompt :**
> Suis `superpowers:test-driven-development`.
>
> **RED.** Dans `test_autoposting_integration.py`, org `autopost_enabled=True`, facture `sent` (revenu déjà posté) :
> - `POST /api/invoices/{id}/payments` : écriture d'encaissement Dr 1000 / Cr 1100 = amount_cad ; balance équilibrée ; le recalcul de statut (`partial`/`paid`) NE crée PAS de 2e écriture de revenu.
> - `DELETE /api/invoices/{id}/payments/{pid}` : l'encaissement est contre-passé (net zéro 1000/1100) ; l'écriture de revenu reste vivante.
> - Idempotence : deux appels au hook avec le même `payment.id` → 1 écriture.
>
> **GREEN.** Dans `server.py` :
> - `add_invoice_payment` (`server.py:3822`) : après insertion du paiement et `_recompute_invoice_status`, garder par `autopost_enabled` + `_safe_autopost(lambda: _autopost_payment(org_id, user_id, inv, payment), "invoices", inv["id"], scope)`.
> - `delete_invoice_payment` (`server.py:3847`) : `_safe_autopost(lambda: _unpost_source_entry(org_id, user_id, "invoice_payment", pid), "invoices", inv["id"], scope)`.
>
> **REFACTOR.** Vérifie qu'une facture passée `paid` via paiements a exactement 2 écritures vivantes (revenu + encaissement).

**Critères d'acceptation :**
- POST payment → encaissement posté (idempotent) ; recompute de statut ne re-poste pas le revenu.
- DELETE payment → encaissement contre-passé, net zéro ; revenu intact.
- Échec n'empêche pas l'ajout/suppression du paiement.

---

## Tâche 9 — Hooks facture supprimée (cascade) + dépenses POST/PUT/DELETE

**Objectif :** cascade de contre-passation à la suppression de facture (§5.4) et cycle complet des dépenses (§5.6/§5.7).

**Subagent prompt :**
> Suis `superpowers:test-driven-development`.
>
> **RED.** Dans `test_autoposting_integration.py`, org `autopost_enabled=True` :
> - **Suppression facture** : facture `sent` + 2 paiements ; `DELETE /api/invoices/{id}` → revenu contre-passé ET les 2 encaissements contre-passés ; net zéro global ; aucun vivant restant pour `source_id`=facture ni pour les `payment.id`.
> - **Dépense POST** : `POST /api/expenses` → 1 écriture de dépense (charge nette + taxes + crédit) équilibrée.
> - **Dépense PUT (montant changé)** : `PUT /api/expenses/{id}` avec `amount` modifié → ancienne écriture contre-passée + nouvelle postée avec le montant à jour ; **1 seul vivant** ; net des deux ≠ 0 (reflète le nouveau montant), mais somme (ancien + miroir) = 0.
> - **Dépense DELETE** : `DELETE /api/expenses/{id}` → contre-passée, net zéro, aucun vivant.
> - `autopost_enabled=False` : aucun de ces hooks ne crée d'écriture.
>
> **GREEN.** Dans `server.py`, garder chaque hook par `autopost_enabled` + `_ensure_chart_seeded` + `_safe_autopost` :
> - `delete_invoice` (`server.py:3876`) : `_unpost_source_entry("invoice", inv_id)` puis, pour chaque `payment` de la facture, `_unpost_source_entry("invoice_payment", payment["id"])`. Modèle : la cascade `_release_bank_transaction` déjà appelée `server.py:3880`.
> - `create_expense` (`server.py:4959`) : `_autopost_expense(org_id, user_id, expense)`.
> - `update_expense` (`server.py:4988`) : régénère → `_unpost_source_entry("expense", id)` puis `_autopost_expense(...)` (toujours régénérer, pas d'optimisation de court-circuit pour cette version).
> - `delete_expense` (`server.py:5037`) : `_unpost_source_entry("expense", id)`. Modèle : cascade `_release_bank_transaction` `server.py:5040`.
>
> **REFACTOR.** Confirme que la suppression physique d'écriture n'est jamais utilisée (uniquement contre-passation).

**Critères d'acceptation :**
- Suppression facture : cascade revenu + tous paiements, net zéro.
- Dépense : POST poste, PUT régénère (1 vivant), DELETE contre-passe.
- `autopost_enabled=False` → aucun effet ; aucun hook ne fait échouer l'op métier.

---

## Tâche 10 — Verrou endpoints manuels (`entry_type=="auto"` → 400)

**Objectif :** empêcher toute mutation manuelle d'une écriture auto (décision #4).

**Subagent prompt :**
> Suis `superpowers:test-driven-development`.
>
> **RED.** Dans `test_autoposting_integration.py` : pose une écriture `entry_type="auto"` via un hook, puis appelle chacun de `PUT /api/ledger/entries/{id}`, `POST /api/ledger/entries/{id}/post`, `POST /api/ledger/entries/{id}/reverse`, `DELETE /api/ledger/entries/{id}` → chacun renvoie **400** avec le message « Écriture générée automatiquement — modifiez le document source ». Une écriture `entry_type="manual"` reste éditable/contre-passable normalement (non-régression Phase 1).
>
> **GREEN.** Dans `server.py`, au début de chacun des 4 endpoints manuels (après chargement de `entry` filtré par org), ajoute :
> ```python
> if entry.get("entry_type") == "auto":
>     raise HTTPException(400, "Écriture générée automatiquement — modifiez le document source")
> ```
> Ne pas toucher `_unpost_source_entry`/`_reverse_entry_internal` (chemin interne, non bloqué).
>
> **REFACTOR.** Confirme que les 4 endpoints continuent de fonctionner pour les écritures manuelles.

**Critères d'acceptation :**
- Les 4 endpoints manuels renvoient 400 sur une écriture `auto` ; message exact.
- Écritures manuelles : comportement Phase 1 inchangé ; contre-passation interne des auto toujours possible.

---

## Tâche 11 — Endpoints `/api/ledger/autopost/status` + `repair`

**Objectif :** diagnostic (couverture, erreurs en attente) et réparation rejouable (§8.1).

**Subagent prompt :**
> Suis `superpowers:test-driven-development`.
>
> **RED.** Dans `test_autoposting_integration.py`, org `autopost_enabled=True` :
> - `GET /api/ledger/autopost/status` (perm `accounting:read`) → `{enabled, expense_default_credit_account, pending_errors, coverage:{invoices_posted, invoices_total_postable, expenses_posted, expenses_total}}`. Après avoir posté 1 facture sur 2 postables → `invoices_posted==1`, `invoices_total_postable==2`.
> - Simule un échec : force un `autopost_error` sur une dépense (compte 5xxx introuvable) ; `status.pending_errors==1`. `POST /api/ledger/autopost/repair` (perm `accounting:write`) → rejoue le post, efface `autopost_error`, `{repaired:1, still_failing:[]}` ; `status.pending_errors==0` ensuite.
> - Isolation : org B n'apparaît pas dans le `coverage` de A.
>
> **GREEN.** Dans `server.py`, ajoute les deux endpoints (RouteGuard permissions comme les endpoints ledger Phase 1). `status` : compte les docs par org (`invoices` `status != draft` avec/sans écriture vivante ; `expenses` idem ; `pending_errors` = docs avec `autopost_error` non-null). `repair` : pour chaque doc avec `autopost_error`, rejoue le mapping approprié via `_safe_autopost` (invoice→`_autopost_invoice_revenue`, expense→`_autopost_expense`) ; renvoie `repaired`/`still_failing`.
>
> **REFACTOR.** Factorise le comptage de couverture avec le backfill (Tâche 12) si le code se recoupe.

**Critères d'acceptation :**
- `status` renvoie le shape exact ; `coverage` filtré par org.
- `repair` rejoue, efface les erreurs réparées, liste les échecs persistants ; idempotent.

---

## Tâche 12 — Endpoint backfill (dry-run + apply, idempotent)

**Objectif :** générer les écritures pour les docs déjà existants, avec aperçu avant application (§7, point ouvert #2).

**Subagent prompt :**
> Suis `superpowers:test-driven-development`.
>
> **RED.** Dans `test_autoposting_integration.py`, org avec 3 factures `sent` (dont 1 déjà postée), leurs paiements, 2 dépenses :
> - `POST /api/ledger/autopost/backfill?dry_run=true` (perm `accounting:write`) → `{would_create:{invoice, invoice_payment, expense}, skipped_existing, period:{start,end}}`, **sans rien écrire** (le nombre d'écritures en base est inchangé). Les docs déjà postés sont dans `skipped_existing`.
> - `dry_run=false` → poste réellement dans l'ordre facture→paiements→dépenses, chaque post via `_safe_autopost` ; renvoie `{created:{...}, failed:[...], period}`.
> - **Idempotence** : relancer `dry_run=false` → `created` tout à 0, `skipped_existing` = tous (aucun doublon ; `_find_live_source_entry` protège).
> - `start`/`end` : par défaut l'exercice courant (`_current_fiscal_year`) ; passer une période exclut les docs hors bornes.
> - Isolation : le backfill de l'org A n'inclut aucun doc de l'org B.
>
> **GREEN.** Dans `server.py`, `POST /api/ledger/autopost/backfill` (query `dry_run` défaut `true`, `start`, `end`). Résout la période (`_current_fiscal_year` si absente). Parcourt `invoices` (`status != draft`) sur `issue_date ∈ [start,end]`, leurs `payments` sur `date ∈ [start,end]`, `expenses` sur `expense_date ∈ [start,end]`, tous filtrés par org. Dry-run : compte via `_find_live_source_entry` sans écrire. Apply : `_ensure_chart_seeded` puis poste chaque source via `_safe_autopost`, ordre facture→paiements→dépenses. Le backfill n'exige PAS `autopost_enabled` (action explicite one-shot).
>
> **REFACTOR.** Confirme qu'un 2e apply ne crée rien.

**Critères d'acceptation :**
- Dry-run ne modifie pas la base ; renvoie les comptes par type + `skipped_existing` + période.
- Apply poste dans l'ordre, protégé, renvoie créés/échecs ; **idempotent** (relance = 0 nouveau).
- Filtré par org et par période ; ne dépend pas de `autopost_enabled`.

---

## Tâche 13 — Endpoint réconciliation P&L `/api/ledger/reconciliation`

**Objectif :** outil de contrôle comptable comparant P&L accrual et GL (§9).

**Subagent prompt :**
> Suis `superpowers:test-driven-development`.
>
> **RED.** Dans `test_autoposting_integration.py`, org `autopost_enabled=True`, après backfill de l'exercice :
> - `GET /api/ledger/reconciliation?start=&end=` (perm `accounting:read`) →
>   `{revenue:{pnl, gl, diff}, expenses:{pnl_gross, gl_net, recoverable_taxes, diff}, balanced}`.
> - **Revenus** : `revenue.gl` (Σ crédits 4000 sur `entry_date ∈ période`) ≈ `revenue.pnl` (`_aggregate_pnl` accrual) ; `|diff| < 0.02`.
> - **Dépenses** : `expenses.gl_net` (Σ débits 5xxx) = `expenses.pnl_gross` (Σ `amount_cad` P&L) − `expenses.recoverable_taxes` (Σ débits 12xx) ; l'écart structurel = les taxes récupérables ; `diff = pnl_gross − (gl_net + recoverable_taxes)` ≈ 0.
> - `balanced == True` quand `|revenue.diff| < 0.02` ET `|expenses.diff| < 0.02`.
> - Cas déséquilibré : une facture avec `autopost_error` (non postée) → `revenue.diff > 0.02`, `balanced == False`.
>
> **GREEN.** Dans `server.py`, `GET /api/ledger/reconciliation` : `revenue.pnl` via `_aggregate_pnl(scope, start, end, basis="accrual")` ; `revenue.gl` = somme des crédits sur le compte 4000 (via `_account_balance` ou agrégation sur `journal_entries` postées, `entry_date ∈ période`, filtré org) ; idem `expenses.gl_net` (Σ débits 5xxx), `recoverable_taxes` (Σ débits 1200/1210/1220), `expenses.pnl_gross` (dépenses P&L brutes). Calcule les `diff` et `balanced` avec le seuil 0.02.
>
> **REFACTOR.** Vérifie la cohérence de la conversion CAD avec `_aggregate_pnl` (même arrondi).

**Critères d'acceptation :**
- Shape exact ; revenus concordent (< 0.02) ; écart dépenses = taxes récupérables ; `balanced` correct.
- Une écriture manquante fait basculer `balanced=false`.

---

## Tâche 14 — Tests intégration bout-en-bout (cycles, isolation, non-régression)

**Objectif :** compléter la couverture spec §11.2 non couverte par les tâches précédentes ; verrouiller les invariants globaux.

**Subagent prompt :**
> Suis `superpowers:test-driven-development` (ici : tests d'abord, correctifs seulement si un test révèle un bug — chaque cas doit passer sans nouvelle logique métier ; sinon appliquer `superpowers:systematic-debugging`).
>
> Dans `test_autoposting_integration.py`, ajoute les cas manquants du spec §11.2 :
> - **Cycle facture complet** : POST facture `draft` (rien) → `sent` (revenu) → paiement (encaissement) → **balance de vérification équilibrée** → suppression paiement (net zéro) → retour `draft` (revenu net zéro). Assertions sur la balance à chaque étape.
> - **Multi-devise** : facture USD → écriture équilibrée, `Σ Dr == Σ Cr`, total Dr 1100 == `total_cad`.
> - **Robustesse compte manquant** : rends 4000 inactif/supprimé → `PUT status sent` renvoie **200** + `autopost_error` posé ; recrée 4000 ; `POST /repair` rejoue ; réconciliation `balanced`.
> - **Isolation cross-org** : org A poste ; org B ne voit aucune écriture de A ; `status`/`backfill`/`reconciliation` de B excluent les docs de A.
> - **Non-régression Phase 1** : journal manuel, écriture d'ouverture, apport propriétaire, balance, bilan — inchangés ; une écriture manuelle n'est JAMAIS touchée par l'auto-posting (contre-passer une facture ne modifie aucune écriture `manual`).
> - **Opt-in global** : `autopost_enabled=False` sur toute la séquence POST facture/paiement/dépense → 0 écriture ; puis `True` → écritures créées.
>
> Fais tourner `cd backend && python -m pytest -q` (toute la suite) : **tout vert**, y compris les tests Phase 1.

**Critères d'acceptation :**
- Tous les cas §11.2 du spec couverts et verts.
- Cible atteinte : ~22 unitaires (test_autoposting.py) + ~26 intégration (test_autoposting_integration.py).
- Suite complète verte ; zéro régression Phase 1.

---

## Tâche 15 — Frontend : onglet Auto-posting + badges + indicateurs d'erreur

**Objectif :** exposer l'auto-posting dans `LedgerPage` (§12).

**Subagent prompt :**
> Suis `superpowers:test-driven-development` pour la logique testable (formatage, mapping d'état) ; pour l'UI, écris des tests de rendu (React Testing Library, comme les composants Phase 1) avant l'implémentation.
>
> Dans `frontend/src/` (repère le fichier `LedgerPage` de la feature #12) :
> - **Onglet « Auto-posting »** gaté `accounting:read` : toggle `autopost_enabled` (`accounting:write`, via `PUT /api/settings/company`), sélecteur `expense_default_credit_account` (Encaisse 1000 / Comptes fournisseurs 2000), carte **couverture** (X/Y factures postées via `GET /api/ledger/autopost/status`), badge `pending_errors` rouge + bouton **« Réparer »** (`POST /api/ledger/autopost/repair`), **assistant backfill** (choix période → dry-run affichant « N écritures seront créées » → confirmation → apply).
> - **Badge « Auto »** sur les écritures `entry_type="auto"` dans l'onglet Journal + lien vers le document source ; boutons édition/contre-passation **masqués** (verrou §8.3).
> - **Indicateur `autopost_error`** (icône d'alerte) sur les listes Factures/Dépenses → renvoie vers l'onglet Auto-posting.
> - Réutilise `RouteGuard`, `hasPermission`, le format CAD existants. Aucune nouvelle lib.
>
> Lance `cd frontend && npm test` (ou la commande de test frontend du repo) : vert.

**Critères d'acceptation :**
- Onglet fonctionnel (toggle, sélecteur, couverture, réparer, assistant backfill dry-run→apply), gaté par permissions.
- Badges auto (édition masquée) + indicateurs d'erreur en place.
- Tests frontend verts ; aucune nouvelle dépendance.

---

## Tâche 16 — Push + mise à jour CLAUDE.md

**Objectif :** livrer (workflow pull-avant / push-après) et documenter la feature.

**Subagent prompt :**
> Suis `superpowers:verification-before-completion` AVANT de pousser.
>
> 1. **Vérification finale** : `cd backend && python -m pytest -q` (tout vert) ; build/tests frontend verts. Colle les sorties comme preuve.
> 2. **CLAUDE.md** (racine repo) : ajoute une section « Grand livre Phase 2 — auto-posting » : flag opt-in `autopost_enabled` (défaut off), `expense_default_credit_account`, écritures `entry_type="auto"` verrouillées (modifier le document source), endpoints `/api/ledger/autopost/{status,backfill,repair}` et `/api/ledger/reconciliation`, limites §13 du spec (dépenses créditées Encaisse par défaut, `amount` TTC, CAD only, clôture annuelle manuelle). Référence le spec et ce plan.
> 3. **Commit** (ne pas committer sur la branche par défaut sans branche dédiée ; suivre le workflow du repo). Message terminé par :
>    ```
>    Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
>    ```
> 4. **Push** conformément au workflow pull-avant / push-après du projet (voir mémoire FacturePro).

**Critères d'acceptation :**
- Suite complète verte, preuve collée.
- CLAUDE.md mis à jour (feature, endpoints, flags, limites, liens spec/plan).
- Poussé selon le workflow du repo ; message de commit conforme.

---

## Definition of Done (globale)

- [ ] `_create_journal_entry` threade `source_type`/`source_id` (rétrocompatible).
- [ ] Migration idempotente + index unique partiel `uniq_live_auto_source`.
- [ ] Primitives idempotentes `_find_live_source_entry`/`_post_source_entry`/`_unpost_source_entry` (contre-passation via le même chemin que `reverse_entry`).
- [ ] `_safe_autopost` : jamais de propagation, `autopost_error` générique horodaté.
- [ ] 3 mappings (facture/paiement/dépense) équilibrés par différence, CAD, taxes ON créées à la volée.
- [ ] Hooks sur 7 endpoints sources, gardés `autopost_enabled`, table de transitions §5.5 respectée, cascade suppression facture.
- [ ] Verrou `entry_type=="auto"` (400) sur les 4 endpoints manuels.
- [ ] Endpoints `status`/`repair`/`backfill` (dry-run + apply idempotent) + `reconciliation`.
- [ ] ~50 tests verts (isolation cross-org, idempotence, net-zéro sur edit/delete, réconciliation, non-régression Phase 1).
- [ ] Frontend : onglet Auto-posting + badges + indicateurs.
- [ ] CLAUDE.md à jour ; poussé.
- [ ] **Invariant** : aucune donnée métier existante mutée ; opt-in ; rollback = `autopost_enabled=false` (§14).
