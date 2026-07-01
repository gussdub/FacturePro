# Organisations multi-tenant (feature #11) — Design

**Statut :** design approuvé 2026-07-01 (brainstorming session avec gussdub)
**Auteur :** Claude (brainstorming + explore-phase sur `backend/server.py`)

## 1. Objectif

Transformer FacturePro d'un modèle **single-tenant par utilisateur** (chaque user = son propre silo de données) en un modèle **multi-tenant par organisation** : plusieurs utilisateurs peuvent partager une même organisation avec des rôles distincts (`owner`, `accountant`, `viewer`) et un système de permissions granulaires éditable par le propriétaire.

Cas d'usage principal : un propriétaire de TPE invite son comptable externe pour qu'il consulte/saisisse les dépenses et produise les rapports fiscaux sans partager son mot de passe personnel. Cas secondaire : associer un employé lecture-seule qui consulte l'état des factures sans pouvoir en créer.

**Contexte codebase :** aujourd'hui toutes les collections métier (`invoices`, `quotes`, `expenses`, `clients`, `products`, `employees`, `company_settings`, `files`, `bank_*`) filtrent par `user_id`. L'abonnement Stripe est attaché au user. Il n'existe **aucun** champ role ou permission. Ce design introduit une collection `organizations` qui absorbe la subscription + les permissions, et bascule toutes les requêtes `user_id` → `organization_id`.

## 2. Décisions de design (brainstorming — fixes)

| # | Question | Décision | Alternatives rejetées |
|---|----------|----------|------------------------|
| 1 | Où loge la subscription Stripe ? | **Sur `organizations`** (`subscription_status`, `stripe_customer_id`, `trial_ends_at`) | Rester sur `users` → briserait le sens : un membre invité ne paie pas. |
| 2 | Comment scope-t-on les données ? | **`organization_id` sur chaque doc métier**, `created_by_user_id` conservé pour audit | Un lookup `users.organization_id` à chaque query → 60 endpoints × 1 lookup = coût inutile ; risque d'erreur. |
| 3 | Modèle de rôles | **3 rôles fixes** : `owner`, `accountant`, `viewer` + permissions éditables par le propriétaire | Custom roles v1 → complexité UI + edge-cases (renommage, suppression) hors scope TPE. |
| 4 | Où stocke-t-on la matrice de permissions ? | **Sur `organizations.role_permissions`** (dict par rôle) — modifiable en Paramètres → Équipe | Hard-code dans le backend → impossible pour l'owner d'assouplir le rôle comptable sans deploy. |
| 5 | Owner-only permissions | **Hard-codées** (`settings:manage`, `billing:manage`, `team:manage`) — non éditables | Rendre tout éditable → un owner pourrait accidentellement transférer la facturation à un viewer = anti-lockout brisé. |
| 6 | Flow d'invitation | **Option 2b : lien signé par email via Resend**, TTL 7 jours, single-use | Ajout direct par email sans acceptation → l'invité ne consent pas ; risque légal PIPEDA. |
| 7 | Peut-on inviter un email déjà user ? | **Oui**. L'endpoint `accept-invite` vérifie le password et rattache le user à l'org. | Refuser → le comptable existant devrait créer un 2e compte, mauvaise UX. |
| 8 | Un user peut-il être dans plusieurs orgs ? | **Non en v1**. `users.organization_id` scalaire. | Multi-org → nécessite un sélecteur d'org à chaque login + explosion des JWTs. Reporté v2. |
| 9 | Migration existante | **Idempotente au boot backend** : chaque user existant devient owner d'une org auto-créée qui reprend son `company_name` | Migration one-shot manuelle → risque de désync entre push code / migration. |
| 10 | Suppression d'un membre | **Soft** : on unset `organization_id` + `role` sur le user ; les docs qu'il a créés restent dans l'org avec `created_by_user_id` intact | Hard-delete → perte d'audit trail ARC (6 ans). |
| 11 | Owner peut-il se retirer lui-même ? | **Non**. Erreur 400 explicite. | Anti-lockout ; le transfert d'ownership est hors scope v1. |
| 12 | Quota scan reçus (feature #8) | **Partagé org-wide** : `scan_count_this_month` et `scan_quota_reset_at` déménagent de `users` → `organizations` | Par-user → un accountant ajouté pourrait doubler la quota gratuitement. |
| 13 | Endpoint pour lire le contexte org courant | **`GET /api/org/me`** retourne org + rôle du user courant + `role_permissions` + membres | Charger tout dans `/api/auth/me` → payload trop gros + confusion des responsabilités. |
| 14 | Gestion CGU/PIPEDA pour invité | Checkbox obligatoire sur `/accept-invite` avec timestamp `pipeda_consent_at` sur le user | Consent implicite → risque légal. |

## 3. Modèle de données

### 3.1 Nouvelle collection `organizations`

```python
{
  "id": str,                              # uuid
  "name": str,                            # copié de user.company_name à la migration
  "owner_id": str,                        # user_id du propriétaire (protection anti-lockout)
  "subscription_status": str,             # "trial" | "active" | "expired" (déplacé de users)
  "stripe_customer_id": str | None,       # déplacé de users si présent
  "trial_ends_at": str | None,            # ISO 8601 (déplacé de users.trial_end_date)
  "role_permissions": {                   # matrice éditable par owner
    "accountant": ["expenses:read", "expenses:write", "invoices:read", ...],
    "viewer":     ["expenses:read", "invoices:read", ...],
  },
  "scan_count_this_month": int,           # déplacé de users (partage quota org-wide)
  "scan_quota_reset_at": str | None,      # déplacé de users
  "created_at": str,                      # ISO 8601 UTC
}
```

**Note importante** : `owner_id` est immutable en v1. Un futur transfert d'ownership (v2) l'assouplirait via un endpoint dédié.

**Index** : `id` (unique), `owner_id` (lookup rapide "quelles orgs possède ce user").

### 3.2 Modifications de la collection `users`

Champs **ajoutés** :

```python
"organization_id": str | None,            # null = user pas encore rattaché (edge case migration)
"role": str,                              # "owner" | "accountant" | "viewer"
"pipeda_consent_at": str | None,          # ISO 8601 — set à l'acceptation d'invite
```

Champs **déplacés vers `organizations`** (à retirer de `users` après migration réussie) :

- `subscription_status`
- `stripe_customer_id`
- `trial_end_date` → `organizations.trial_ends_at`
- `scan_count_this_month`
- `scan_quota_reset_at`

Champs **conservés sur `users`** : `id`, `email`, `company_name` (legacy, non affiché), `is_active`, `created_at`, `receipt_ocr_consent_at`.

**Note stratégie transition** : pendant la période de coexistence (2-4 semaines post-deploy), le backend **lit** depuis `organizations` en priorité et **fallback** sur `users` si l'org n'existe pas encore. Après stabilisation, un script `drop_legacy_user_fields.py` retire les champs déplacés.

### 3.3 Nouvelle collection `invitations`

```python
{
  "id": str,                              # uuid
  "organization_id": str,                 # org qui invite
  "email": str,                           # normalisé lowercase
  "role": str,                            # "accountant" | "viewer" (jamais "owner")
  "token": str,                           # secrets.token_urlsafe(32) — 43 chars
  "expires_at": str,                      # ISO 8601 UTC (created + 7 jours)
  "status": str,                          # "pending" | "accepted" | "revoked" | "expired"
  "invited_by_user_id": str,              # audit
  "created_at": str,
  "consumed_at": str | None,              # ISO 8601 au moment de l'acceptation
}
```

**Index** : `token` (unique, sparse), `organization_id + status`, `email + status` (pour empêcher les invites dupliquées "pending").

### 3.4 Modifications sur les collections métier

Toutes les collections listées ci-dessous reçoivent un nouveau champ **`organization_id`** :

- `invoices`, `quotes`, `expenses`, `clients`, `products`, `employees`
- `company_settings`, `files`
- `bank_mappings`, `bank_imports`, `bank_transactions`
- `payment_transactions`, `trial_notifications`, `quote_tokens`

Le champ `user_id` est **renommé** en `created_by_user_id` (audit trail, obligatoire, conservé pour toute la vie du document).

**Compatibilité pendant la transition** : les endpoints lisent `organization_id` en priorité et **fallback** sur `user_id == current_user.id` si `organization_id` est absent (docs pré-migration). Après backfill startup complet, ce fallback est retiré.

### 3.5 Codes de permissions (constantes serveur)

```python
# backend/server.py — constantes proches de EXPENSE_CATEGORIES
PERMISSIONS_EDITABLE = [
    "expenses:read",   "expenses:write",
    "invoices:read",   "invoices:write",
    "quotes:read",     "quotes:write",
    "clients:read",    "clients:write",
    "products:read",   "products:write",
    "employees:read",  "employees:write",
    "reports:read",
    "bank:read",       "bank:write",
    "receipts:scan",
]

PERMISSIONS_OWNER_ONLY = [
    "settings:manage",  # company_info, entity_type, province, home/vehicle %
    "billing:manage",   # Stripe subscription + customer portal
    "team:manage",      # invite, remove, change role, edit permissions
]

# Matrice par défaut, appliquée à la création de toute nouvelle org
DEFAULT_ROLE_PERMISSIONS = {
    "accountant": list(PERMISSIONS_EDITABLE),  # tout coché
    "viewer": [
        "expenses:read", "invoices:read", "quotes:read",
        "clients:read", "products:read", "employees:read",
        "reports:read", "bank:read",
        # pas de :write, pas de receipts:scan
    ],
}
```

L'`owner` a **inhérentement** tous les codes (éditables + owner-only) via la résolution dynamique dans `get_current_user_with_permissions` (cf. §4).

## 4. Auth middleware refactor

### 4.1 Nouveau modèle Pydantic

```python
class CurrentUser(BaseModel):
    id: str
    email: str
    organization_id: str
    role: str                      # "owner" | "accountant" | "viewer"
    permissions: list[str]         # résolues à chaque requête (pas cachées)
    is_exempt: bool                # gussdub@gmail.com toujours actif
```

### 4.2 Résolution des permissions

```python
def _resolve_permissions(org: dict, role: str) -> list[str]:
    if role == "owner":
        return list(PERMISSIONS_EDITABLE) + list(PERMISSIONS_OWNER_ONLY)
    role_perms = (org.get("role_permissions") or {}).get(role, [])
    # Sécurité : n'accepter que des codes connus (protège contre role_permissions polluté)
    return [p for p in role_perms if p in PERMISSIONS_EDITABLE]
```

### 4.3 `get_current_user_with_access` refactor

L'endpoint existant devient l'implémentation par défaut. Nouvelle logique :

```python
def get_current_user_with_access(credentials: HTTPAuthorizationCredentials = Depends(security)) -> CurrentUser:
    payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
    user_id = payload["sub"]
    user = db.users.find_one({"id": user_id})
    if not user or not user.get("is_active"):
        raise HTTPException(401, "Utilisateur inactif ou introuvable")
    org_id = user.get("organization_id")
    if not org_id:
        # Fallback pré-migration : reconstruire une org virtuelle à la volée
        org = _synthesize_solo_org_from_user(user)  # cf 6.3
    else:
        org = db.organizations.find_one({"id": org_id})
        if not org:
            raise HTTPException(500, "Organisation introuvable — contactez le support")
    # Subscription check (déjà présent sur users, à muter sur org)
    _check_subscription_active(org, user)
    return CurrentUser(
        id=user["id"], email=user["email"], organization_id=org["id"],
        role=user.get("role", "owner"),
        permissions=_resolve_permissions(org, user.get("role", "owner")),
        is_exempt=user["email"] in EXEMPT_USERS,
    )
```

### 4.4 Dependency `require_permission`

```python
def require_permission(perm_code: str):
    def _dep(current_user: CurrentUser = Depends(get_current_user_with_access)):
        if perm_code not in current_user.permissions:
            raise HTTPException(403, f"Permission requise : {perm_code}")
        return current_user
    return _dep
```

**Application** : chaque endpoint métier remplace `Depends(get_current_user_with_access)` par `Depends(require_permission("<code>"))`. Table de mapping (extraite du context d'explore) :

| Endpoint (méthode + path) | Permission requise |
|---|---|
| `GET /api/expenses`, `/api/expenses/*` (read) | `expenses:read` |
| `POST/PUT/DELETE /api/expenses/*` | `expenses:write` |
| `POST /api/expenses/scan-receipt` | `receipts:scan` |
| `GET /api/invoices`, `/api/invoices/{id}` | `invoices:read` |
| `POST/PUT/DELETE /api/invoices*`, payments, remind, send | `invoices:write` |
| `GET /api/quotes*` | `quotes:read` |
| `POST/PUT/DELETE /api/quotes*` | `quotes:write` |
| `GET /api/clients` | `clients:read` |
| `POST/PUT/DELETE /api/clients*` | `clients:write` |
| `GET /api/products` | `products:read` |
| `POST/PUT/DELETE /api/products*` | `products:write` |
| `GET /api/employees` | `employees:read` |
| `POST/PUT/DELETE /api/employees*` | `employees:write` |
| `GET /api/reports/*`, `GET /api/dashboard/*` | `reports:read` |
| `GET /api/bank/*` | `bank:read` |
| `POST/PUT/DELETE /api/bank/*` | `bank:write` |
| `GET/PUT /api/settings`, `/api/company` | `settings:manage` |
| `POST /api/subscribe`, portal Stripe | `billing:manage` |
| `POST/GET/DELETE /api/org/invitations`, `/api/org/members/*`, `PUT /api/org/role-permissions` | `team:manage` |

**Endpoints laissés sans `require_permission`** : `/api/auth/*` (public ou self), `/api/expense-categories` (public), `/api/health`, `/api/org/me` (tout membre authentifié).

### 4.5 Scoping des queries : `organization_id` remplace `user_id`

Tous les filtres MongoDB de la forme `{"user_id": current_user.id}` deviennent `{"organization_id": current_user.organization_id}`. Toutes les créations écrivent :

```python
doc["organization_id"] = current_user.organization_id
doc["created_by_user_id"] = current_user.id
```

## 5. API REST

### 5.1 GET /api/org/me — contexte organisation

```
GET /api/org/me
  Auth requise (tout membre)
  → 200 {
    "organization": {
      "id": str, "name": str, "owner_id": str,
      "subscription_status": str, "trial_ends_at": str | None,
      "role_permissions": dict,
      "scan_count_this_month": int, "scan_quota_limit": 200,
    },
    "current_user": {
      "id": str, "email": str, "role": str,
      "permissions": [str, ...],
    },
    "members": [
      {"id": str, "email": str, "role": str, "created_at": str}, ...
    ]
  }
  → 401 si token invalide
  → 500 si organisation orpheline (log + alerte)
```

### 5.2 PUT /api/org/role-permissions — éditer la matrice

```
PUT /api/org/role-permissions
  Auth requise + team:manage
  body: {
    "role": "accountant" | "viewer",
    "permissions": ["expenses:read", "expenses:write", ...]
  }
  Validation :
    - role ∈ {"accountant", "viewer"} — 400 si "owner"
    - chaque code ∈ PERMISSIONS_EDITABLE — 400 si code inconnu ou owner-only
  → 200 {"role": str, "permissions": [...]}
  → 400 si validation KO
  → 403 si pas team:manage
```

### 5.3 POST /api/org/invitations — inviter un membre

```
POST /api/org/invitations
  Auth requise + team:manage
  body: {"email": str, "role": "accountant" | "viewer"}
  Validation :
    - email format valide (regex simple : /^[^@]+@[^@]+\.[^@]+$/)
    - role ∈ {"accountant", "viewer"} — 400 si "owner"
    - pas d'invitation "pending" déjà en cours pour ce email dans cette org — 409
    - le email n'est PAS déjà membre actif de cette org — 409
  Actions :
    1. Génère token = secrets.token_urlsafe(32)
    2. Insert dans db.invitations {status: "pending", expires_at: now + 7j}
    3. Envoie email via Resend : link https://facturepro.ca/accept-invite?token=<token>
       + expéditeur noreply@facturepro.ca
       + sujet "Invitation à rejoindre {org.name} sur FacturePro"
  → 201 {"id": str, "email": str, "role": str, "expires_at": str}
  → 400 si validation KO
  → 409 si duplicate pending ou déjà membre
  → 502 si Resend échoue (rollback : delete invitation)
```

### 5.4 GET /api/org/invitations — lister les invitations

```
GET /api/org/invitations?status=pending
  Auth requise + team:manage
  → 200 [{
    "id": str, "email": str, "role": str,
    "status": str, "expires_at": str, "created_at": str
  }, ...]
```

Par défaut retourne uniquement `pending`. Filtre `?status=all` pour tout voir.

### 5.5 DELETE /api/org/invitations/{id} — révoquer

```
DELETE /api/org/invitations/{invitation_id}
  Auth requise + team:manage
  Actions : set status = "revoked" (jamais hard delete — audit)
  → 204
  → 404 si invitation inconnue ou n'appartient pas à l'org
  → 400 si déjà "accepted"
```

### 5.6 POST /api/auth/accept-invite — endpoint public

```
POST /api/auth/accept-invite
  Rate-limit : 5 requêtes / min / IP (via slowapi ou middleware custom)
  body: {
    "token": str,
    "password": str,               # requis si nouvel user, requis pour verify si user existant
    "pipeda_consent": bool         # doit être true, sinon 400
  }
  Validation :
    - pipeda_consent === true → sinon 400 "Vous devez accepter les CGU/PIPEDA"
    - token trouvé dans db.invitations avec status="pending" → sinon 404
    - expires_at > now → sinon 410 "Invitation expirée"
    - status != "revoked" → sinon 410
  Actions :
    - Cherche user par email (case-insensitive)
    - Si user n'existe pas :
        - Crée user {email, is_active: true, created_at: now, pipeda_consent_at: now,
                     organization_id: invitation.org_id, role: invitation.role}
        - Hash bcrypt du password → db.user_passwords
    - Si user existe :
        - Vérifie password (bcrypt.checkpw)
        - Si le user est déjà dans une org → 409 "Cet email est déjà dans une organisation"
        - Update user : organization_id = invitation.org_id, role = invitation.role,
                        pipeda_consent_at = now
    - Update invitation : status = "accepted", consumed_at = now
    - Génère JWT (comme /api/auth/login)
  → 200 {"access_token": str, "token_type": "bearer", "user": {...}}
  → 400 pipeda_consent manquant
  → 401 password invalide (user existant)
  → 404 token inconnu
  → 409 user déjà rattaché à une org
  → 410 token expiré ou révoqué
  → 429 rate limit
```

**Note sécurité** : renvoyer 401 (au lieu de 404) si password invalide sur un user existant évite d'exposer l'existence d'un user par la simple présentation du token.

### 5.7 PUT /api/org/members/{user_id}/role — changer le rôle

```
PUT /api/org/members/{user_id}/role
  Auth requise + team:manage
  body: {"role": "accountant" | "viewer"}
  Validation :
    - target user est dans l'org — 404 sinon
    - target user != org.owner_id — 400 "Impossible de modifier le rôle du propriétaire"
    - role ∈ {"accountant", "viewer"} — 400 sinon
  → 200 {"user_id": str, "role": str}
```

### 5.8 DELETE /api/org/members/{user_id} — retirer un membre

```
DELETE /api/org/members/{user_id}
  Auth requise + team:manage
  Validation :
    - target user est dans l'org — 404 sinon
    - target user != org.owner_id — 400 "Le propriétaire ne peut pas être retiré"
    - target user != current_user.id — 400 "Vous ne pouvez pas vous retirer vous-même"
  Actions (soft) :
    - $unset organization_id, role sur users
    - Les documents créés par ce user conservent created_by_user_id (audit)
  → 204
```

### 5.9 Modifications aux endpoints existants

| Endpoint | Modification |
|---|---|
| `GET /api/auth/me` | Ne renvoie plus `subscription_status`, `trial_end_date`, `scan_count_this_month`, `scan_quota_limit` (déménagent vers `/api/org/me`). Renvoie `organization_id`, `role`, `permissions`. **Transition** : garde les anciens champs pendant 4 semaines pour compat frontend. |
| `POST /api/auth/register` | Après création du user, crée automatiquement une organisation `{name: company_name, owner_id: user.id, subscription_status: "trial", trial_ends_at: now + 14j, role_permissions: DEFAULT_ROLE_PERMISSIONS}`. Set `user.organization_id = new_org.id`, `user.role = "owner"`. |
| `POST /api/subscribe`, portal Stripe | Cherche `stripe_customer_id` sur `organizations` au lieu de `users`. |
| `POST /api/expenses/scan-receipt` | `_check_and_bill_scan` opère sur `db.organizations` (matched par `organization_id`) au lieu de `db.users`. |

## 6. Migration (idempotente au démarrage)

Ajoutée dans le bloc `_run_startup_migrations()` de `server.py`, après les migrations existantes (`pst_number → qst_number`, `db.files.purpose`).

### 6.1 Étapes séquentielles

```python
def migrate_organizations_v1():
    """Idempotente. Safe à exécuter à chaque boot."""
    # Étape 1 : pour chaque user sans organization_id, créer une org
    users_without_org = list(db.users.find({"organization_id": {"$exists": False}}))
    for user in users_without_org:
        org_id = str(uuid.uuid4())
        org_doc = {
            "id": org_id,
            "name": user.get("company_name") or user["email"],
            "owner_id": user["id"],
            "subscription_status": user.get("subscription_status", "trial"),
            "stripe_customer_id": user.get("stripe_customer_id"),
            "trial_ends_at": user.get("trial_end_date"),
            "role_permissions": DEFAULT_ROLE_PERMISSIONS,
            "scan_count_this_month": user.get("scan_count_this_month", 0),
            "scan_quota_reset_at": user.get("scan_quota_reset_at"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        db.organizations.insert_one(org_doc)
        db.users.update_one(
            {"id": user["id"]},
            {"$set": {"organization_id": org_id, "role": "owner"}}
        )
        # Étape 2 : backfill organization_id sur toutes les collections métier
        for coll_name in [
            "invoices", "quotes", "expenses", "clients", "products", "employees",
            "company_settings", "files", "bank_mappings", "bank_imports",
            "bank_transactions", "payment_transactions", "trial_notifications",
            "quote_tokens",
        ]:
            db[coll_name].update_many(
                {"user_id": user["id"], "organization_id": {"$exists": False}},
                [{"$set": {
                    "organization_id": org_id,
                    "created_by_user_id": "$user_id",
                }}]
            )

    # Étape 3 : indexes
    db.organizations.create_index("id", unique=True)
    db.organizations.create_index("owner_id")
    db.invitations.create_index("token", unique=True, sparse=True)
    db.invitations.create_index([("organization_id", 1), ("status", 1)])
    db.invitations.create_index([("email", 1), ("status", 1)])
    for coll_name in [...]:  # même liste
        db[coll_name].create_index("organization_id")

    print(f"MIGRATION organizations_v1 : {len(users_without_org)} orgs créées")
```

### 6.2 Idempotence

Chaque étape est protégée par un check d'existence (`{"organization_id": {"$exists": False}}`). Ré-exécution = no-op.

### 6.3 Fallback si l'auth middleware voit un user sans org (course condition)

Si un user existant se connecte avant que la migration ne l'ait traité (ex : boot en cours, timing avec Render redéploiement), `_synthesize_solo_org_from_user` construit une org **virtuelle** en mémoire :

```python
def _synthesize_solo_org_from_user(user: dict) -> dict:
    return {
        "id": f"pending-{user['id']}",
        "name": user.get("company_name") or user["email"],
        "owner_id": user["id"],
        "subscription_status": user.get("subscription_status", "trial"),
        "trial_ends_at": user.get("trial_end_date"),
        "role_permissions": DEFAULT_ROLE_PERMISSIONS,
        "scan_count_this_month": user.get("scan_count_this_month", 0),
    }
```

Le user reste "owner" implicite et n'a que ses données. Aucune écriture n'est faite dans cette branche (les inserts métier utiliseront `organization_id = "pending-<user_id>"` — le prochain boot les rattachera à la vraie org via un fixup dans la migration).

### 6.4 Retrait des champs legacy (script one-shot post-stabilisation)

Après 4 semaines de coexistence sans incident, exécuter `backend/scripts/drop_legacy_user_fields.py` :

```python
db.users.update_many({}, {"$unset": {
    "subscription_status": "", "stripe_customer_id": "",
    "trial_end_date": "", "scan_count_this_month": "",
    "scan_quota_reset_at": "",
}})
```

Puis, pour chaque collection métier, `$unset: user_id` **seulement après confirmation que `created_by_user_id` est peuplé partout**.

## 7. Frontend

### 7.1 Nouveau tab Settings « Équipe »

Dans `SettingsPage`, ajouter un onglet visible **uniquement si** `permissions.includes("team:manage")`.

Trois sections :

1. **Membres actifs** — table (email, rôle, "Ajouté le"). Actions par ligne :
   - Dropdown pour changer le rôle (`accountant` ↔ `viewer`, désactivé pour l'owner)
   - Bouton "Retirer" (désactivé pour l'owner et le current_user)
2. **Invitations en cours** — liste (email, rôle, expires_at). Bouton "Révoquer" par ligne.
3. **Bouton "Inviter un membre"** — ouvre un modal : email + dropdown rôle → POST `/api/org/invitations`. Toast de succès ; erreurs 409 (duplicate) et 400 (email invalide) affichées inline.

**Section additionnelle "Rôles & permissions"** (sous la section membres) :
- 2 lignes (accountant, viewer)
- Chaque ligne = liste de checkboxes pour les `PERMISSIONS_EDITABLE`
- Bouton "Enregistrer" par ligne → PUT `/api/org/role-permissions`
- Groupement visuel des permissions par domaine (Dépenses, Factures, Devis, Clients, etc.) pour lisibilité

### 7.2 Page publique `/accept-invite`

Nouvelle route (navigation manuelle via `window.history` — pattern existant).

Format URL : `https://facturepro.ca/accept-invite?token=<token>`.

Comportement :
1. Au mount, GET `/api/org/invitations/preview?token=<token>` (nouvel endpoint public read-only qui renvoie `{email, org_name, role}` sans exposer le token) — permet d'afficher "Vous êtes invité à rejoindre **{org_name}** en tant que **{role}**".
2. Form :
   - Email affiché read-only (issu du preview)
   - Password + confirmation
   - Checkbox "J'accepte les [CGU](/cgu) et la [politique de confidentialité PIPEDA](/privacy)" — obligatoire
3. Submit → POST `/api/auth/accept-invite` avec `{token, password, pipeda_consent: true}`
4. Sur succès : stocke le JWT + redirect `/dashboard`
5. Erreurs affichées inline : token expiré (410), password invalide (401), déjà rattaché (409)

### 7.3 AuthContext expose `permissions`

`AuthContext.js` fetch `/api/org/me` après le login (à côté de `/api/auth/me`) et stocke `permissions[]`, `role`, `organization` dans le context.

Nouveaux helpers :

```js
const { hasPermission } = useAuth();
hasPermission("expenses:write");   // true / false
```

### 7.4 Route guards par permission

Layout sidebar : chaque entrée de menu vérifie `hasPermission("<code>:read")` et se cache si false.

| Route | Permission requise pour voir |
|---|---|
| `/dashboard` | (aucune — tout membre) |
| `/invoices` | `invoices:read` |
| `/quotes` | `quotes:read` |
| `/clients` | `clients:read` |
| `/products` | `products:read` |
| `/employees` | `employees:read` |
| `/expenses` | `expenses:read` |
| `/bank` (rapprochement) | `bank:read` |
| `/reports` | `reports:read` |
| `/settings` (onglet Équipe) | `team:manage` |
| `/settings` (autres onglets) | `settings:manage` |
| `/subscription` | `billing:manage` |

**Composant `<RouteGuard permission="expenses:read">`** wrapper qui redirige vers `/dashboard` avec toast "Accès refusé" si permission manquante.

### 7.5 Boutons désactivés dans les pages

Dans chaque page, les boutons d'action sont conditionnés :

- ExpensesPage : boutons "Nouvelle dépense" et "Scanner reçu" cachés si `!hasPermission("expenses:write")` (ou "receipts:scan" pour scan)
- InvoicesPage : bouton "Nouvelle facture", "Payment", "Remind" cachés si `!hasPermission("invoices:write")`
- Idem pour Quotes, Clients, Products, Employees

## 8. Sécurité

| Menace | Mitigation |
|---|---|
| **Élévation de privilège via `PUT /api/org/role-permissions`** injectant `settings:manage` sur un viewer | `_resolve_permissions` filtre à `PERMISSIONS_EDITABLE`. Owner-only permissions ne sont **jamais** dans la matrice, hardcodées dans le résolveur. |
| **Fuite cross-org via oubli de filtre `organization_id`** | Grep CI (ou pre-commit hook) sur `find_one({"user_id"` et `find({"user_id"` dans `server.py`. Après la migration, ces patterns doivent disparaître. Tests d'intégration vérifient l'isolation. |
| **Token invitation brute-force** | `secrets.token_urlsafe(32)` = ~256 bits d'entropie. Rate-limit 5/min/IP sur `/api/auth/accept-invite`. TTL 7j. Single-use (status → "accepted"). |
| **Enumération d'emails via `/accept-invite`** | Le preview endpoint ne renvoie l'email QUE si le token est valide et pending. Un token inconnu → 404 générique. Le status 401 (password) vs 404 (token) : accepté car nécessite déjà de posséder un token valide. |
| **User existant piégé sur `/accept-invite`** avec ré-utilisation de son password | POST `/accept-invite` avec user existant vérifie strictement le password bcrypt. En cas d'échec 3× : rate limit s'active. Pas de tentative silencieuse d'auto-connexion. |
| **Owner accidentellement lockout** | (1) Owner ne peut pas se retirer lui-même (400). (2) Owner ne peut pas être `DELETE`. (3) Le rôle owner ne peut pas être changé via `PUT /members/{id}/role`. (4) `owner_id` de l'org est immutable en v1. |
| **Consent PIPEDA manquant** | POST `/accept-invite` refuse si `pipeda_consent !== true`. Timestamp sauvegardé sur `users.pipeda_consent_at`. |
| **Injection SQL/NoSQL via `email` de l'invitation** | Validation regex + normalisation lowercase avant insert. Le champ est utilisé dans `find_one({"email": ...})` — pymongo escape par défaut, pas de string concat. |
| **Cascade de suppression accidentelle** | Retrait d'un member = soft (`$unset`). Aucune donnée métier n'est touchée. |
| **Fuite du `token` dans les logs Resend** | Le token est log-safe (opaque, non-devinable) mais évité en logs : on log `invitation.id`, jamais `invitation.token`. |
| **Session détournée après changement de rôle** | Les permissions sont résolues à **chaque** requête depuis `db.organizations.role_permissions`. Un changement de matrice s'applique immédiatement au prochain call API. Pas de cache TTL. |
| **Timing attack sur bcrypt.checkpw dans `/accept-invite`** | Utilisation directe de `bcrypt.checkpw` (constant-time). Pas de comparaison manuelle. |

## 9. Tests

### 9.1 Unitaires — `backend/tests/test_organizations.py`

- `_resolve_permissions` : owner → toutes perms ; accountant avec matrice défaut → perms attendues ; viewer → perms attendues ; codes owner-only dans matrice → ignorés ; codes inconnus → ignorés.
- `_synthesize_solo_org_from_user` : reconstitution correcte depuis un user pré-migration.
- Migration `migrate_organizations_v1` :
  - Boot 1 : 1 user solo → 1 org créée + user rattaché + 5 docs métier backfillés.
  - Boot 2 (re-run) : no-op, aucun doc modifié.
  - User existant SANS `company_name` → org.name = user.email (fallback).
  - Backfill préserve `created_by_user_id` = ancien `user_id`.
- Validation `POST /api/org/role-permissions` : refuse "owner", refuse codes owner-only, refuse codes inconnus.

### 9.2 Intégration — `backend/tests/test_organizations_integration.py`

- **Isolation cross-org** : user A crée une dépense, user B (autre org) tente GET `/api/expenses/{id_de_A}` → 404 (ou empty list sur `GET /api/expenses`). Idem invoices, quotes, clients.
- **Permissions viewer** :
  - GET `/api/expenses` → 200
  - POST `/api/expenses` → 403 "Permission requise : expenses:write"
  - POST `/api/expenses/scan-receipt` → 403
  - GET `/api/settings` → 403
- **Permissions accountant** :
  - Toutes les writes métier → 200
  - PUT `/api/org/role-permissions` → 403
  - POST `/api/org/invitations` → 403
- **Flow invitation complet** :
  - Owner POST /invitations → 201 + email envoyé (mock Resend).
  - GET /invitations → liste avec l'invite en pending.
  - New user POST /accept-invite avec pipeda_consent=false → 400.
  - New user POST /accept-invite valid → 200 + JWT + user créé + org.id sur user.
  - Second POST /accept-invite avec même token → 410 "Invitation déjà consommée".
  - Owner DELETE /invitations/{id_accepted} → 400.
  - Owner DELETE /invitations/{id_pending} → 204.
  - Invitation expirée (mutate `expires_at` en DB à J-8) → POST /accept-invite → 410.
- **User existant accepte une invite** :
  - User existe (solo dans une autre org) → 409.
  - User existe (pas d'org) → OK, rattaché.
  - User existe avec mauvais password → 401.
- **Owner protégé** :
  - PUT /members/{owner_id}/role → 400.
  - DELETE /members/{owner_id} → 400.
  - DELETE /members/{current_user.id} (owner qui tente de se retirer) → 400.
- **Permissions dynamiquement modifiées** :
  - Owner retire `expenses:read` pour viewer.
  - Viewer refresh token → GET /expenses → 403.
- **Migration à la volée** :
  - Insert un user sans `organization_id` en DB directement.
  - Boot backend → migration passe → user a `organization_id` + `role: owner`.

### 9.3 E2E manuel

- Créer un compte owner, aller dans Paramètres → Équipe, inviter un email accountant.
- Recevoir l'email (Resend inbox), cliquer le lien.
- Accepter avec un nouvel account : compte créé, connecté sur l'org, sidebar affiche toutes les entrées writables.
- Owner change matrice viewer : retire `bank:read`.
- Second user (viewer) se reconnecte, l'onglet "Rapprochement" disparaît de la sidebar.
- Owner retire l'accountant : accountant ne peut plus se login sur l'org (redirigé vers écran "Aucune organisation").
- Test consent PIPEDA absent → checkbox obligatoire.
- Test rate limit /accept-invite : 6 requêtes en 1 min depuis même IP → 429.

**Cible : ~50 tests** (~15 unitaires + ~30 intégration + ~10 E2E manuels).

## 10. Limites v1 / Hors scope

- **Custom roles** (au-delà de owner / accountant / viewer)
- **SSO / SAML** — pas d'IdP externe
- **Audit log** ("qui a créé quoi, quand") — `created_by_user_id` existe mais pas d'endpoint de consultation
- **2FA** — reporté
- **Multi-org par user** — un user = une org en v1
- **Notifications in-app** ("nouveau membre rejoint")
- **Suppression physique** d'un user (`is_deleted` non implémenté sur users)
- **Transfert d'ownership** entre users
- **Facturation pro-rata** si l'org ajoute des membres en cours de mois — Stripe plan reste flat $15 CAD/mois, quota scan reçus reste 200/org/mois
- **Onboarding wizard** pour l'accountant à sa 1re connexion (bienvenue, tour du produit)
- **Email de notification à l'owner** quand un membre accepte l'invite (v1.1)
- **Recherche/filtre** dans la liste des membres (v1 : liste plate)
- **Limite de membres** par org — v1 : aucun (raisonnable à 5-10 en pratique TPE)

## 11. Rollback plan

**Scénarios et procédures :**

1. **Migration corrompt des données** :
   - Détection : erreurs 500 en masse sur `/api/expenses` ou autres reads.
   - Action immédiate : rollback Render à la version N-1 (bouton "Redeploy previous").
   - Recovery : les docs métier ont `organization_id` set MAIS `user_id` legacy toujours présent (transition = 4 semaines). Les anciennes queries `{"user_id": current_user.id}` continuent à matcher. Aucune donnée perdue.
   - Post-mortem : identifier le bug de migration, patch, re-deploy.

2. **Endpoint `require_permission` bloque légitimement un owner** :
   - Detection : owner reporte "Accès refusé" sur son propre écran.
   - Hotfix Vercel : temporairement bypass `hasPermission` côté frontend (tous les boutons visibles).
   - Backend fix : owner permissions résolues correctement (bug dans `_resolve_permissions`).

3. **Resend rate limit ou down** :
   - Detection : POST /invitations retourne 502 en masse.
   - Rollback : pas nécessaire — feature dégradée mais autres endpoints intacts.
   - Workaround : owner peut copier-coller manuellement le lien depuis la DB (support intervention).

4. **User pré-migration bloqué par le fallback `_synthesize_solo_org_from_user`** :
   - Detection : user reporte "org.id = pending-<user_id>" dans /api/org/me.
   - Fix : re-lancer manuellement `migrate_organizations_v1()` via un endpoint admin one-shot.

5. **Rollback complet de la feature** :
   - Redéployer version pré-feature #11 sur Render + Vercel.
   - Documents métier ont `organization_id` et `created_by_user_id` en trop — ignorés par l'ancien code.
   - Collection `organizations` et `invitations` laissées en place (pas de perte de données).
   - Champs `users.subscription_status` etc. n'ont **pas encore** été retirés (le drop script est séparé, exécuté à J+28). Donc l'ancien code retrouve ses données là où il les attend.

**Point de non-retour** : le script `drop_legacy_user_fields.py` (§6.4). **Ne pas** l'exécuter tant que la feature n'a pas 4 semaines de stabilité prod.

## 12. Rollout

1. Ajout des constantes `PERMISSIONS_*` et `DEFAULT_ROLE_PERMISSIONS` dans `server.py`.
2. Ajout de `migrate_organizations_v1()` dans le bloc startup.
3. Refactor de `get_current_user_with_access` + ajout `require_permission`.
4. Décorer les ~60 endpoints métier avec `require_permission("<code>")`.
5. Ajouter les ~15 nouveaux endpoints (`/api/org/*`).
6. Frontend : ajouter le tab Équipe, la page `/accept-invite`, l'expose `permissions[]` dans AuthContext, les route guards.
7. Tests : ~50 tests ajoutés (unit + integration).
8. Push main → Render redéploie (migration s'exécute au boot) → Vercel redéploie.
9. E2E manuel avec un vrai compte accountant invité.
10. Monitoring 4 semaines. Après stabilité : exécution `drop_legacy_user_fields.py`.

**Pas de feature flag** — le refactor est trop profond pour un toggle propre. La migration idempotente + le fallback `_synthesize_solo_org_from_user` couvrent les cas de course.

## 13. Impact estimé

- **Backend** : ~60 endpoints décorés avec `require_permission` (~60 lignes de diff), ~15 nouveaux endpoints (~400 lignes), 1 migration (~60 lignes), refactor auth (~80 lignes). Total : **~600 lignes ajoutées, ~120 lignes modifiées**.
- **Frontend** : 1 nouveau tab Settings (~250 lignes), 1 page publique `/accept-invite` (~150 lignes), context refactor (~50 lignes), route guards (~40 lignes). Total : **~500 lignes ajoutées**.
- **Tests** : ~50 tests, **~800 lignes**.
- **Nouvelles collections** : `organizations`, `invitations`.
- **Env vars nouvelles** : aucune (Resend déjà configuré pour les factures).
- **Coût opérationnel** : négligeable (0 appel externe supplémentaire hors Resend, déjà utilisé).
