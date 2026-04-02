# FacturePro - PRD

## Original Problem Statement
Billing software "FacturePro" for Canadian businesses (French-language).

## Architecture
- **Frontend**: React modular (15 fichiers) on port 3000
- **Backend**: FastAPI + pymongo sync on port 8001
- **Database**: MongoDB
- **Storage**: Emergent Object Storage (logos, recus)
- **Brand Colors**: #00A08C, #47D2A7, #008F7A

## Implemented (2026-02-04)
- [x] Auth (register, login, forgot-password, reset-password)
- [x] Clients CRUD
- [x] Products CRUD
- [x] Invoices CRUD with Canadian taxes (QC/ON)
- [x] Quotes CRUD + convert to invoice
- [x] Employees CRUD
- [x] Expenses CRUD with approval workflow
- [x] Company Settings with drag-and-drop logo upload
- [x] Dashboard stats
- [x] CSV exports
- [x] SVG logo (no external URL dependency)
- [x] File upload via Emergent Object Storage
- [x] Refactored monolith into modular components
- [x] pymongo sync backend (works on Render + Emergent)

## Backlog
### P1
- Stripe subscription ($15/mois CAD, 14 jours trial, gussdub@gmail.com exempt)
- Expense receipt file upload (drag & drop)

### P2
- PDF export for invoices
- Quote-to-invoice conversion in UI
- Employee expense approval workflow

### P3
- UI/UX polish
- Custom domain deployment (facturepro.ca)

## Key Files
- `/app/backend/server.py` - Backend (pymongo sync)
- `/app/frontend/src/App.js` - Router
- `/app/frontend/src/config.js` - Config
- `/app/frontend/src/context/AuthContext.js` - Auth
- `/app/frontend/src/components/` - Layout, FactureProLogo, etc.
- `/app/frontend/src/pages/` - All pages
- `/app/DEPLOYMENT_GUIDE.md` - Render deployment guide
