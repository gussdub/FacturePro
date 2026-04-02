# FacturePro - PRD

## Original Problem Statement
Billing software "FacturePro" for Canadian businesses (French-language).

## Architecture
- **Frontend**: React modular (15+ fichiers) on port 3000
- **Backend**: FastAPI + pymongo sync on port 8001
- **Database**: MongoDB Atlas
- **Storage**: Emergent Object Storage (logos, recus)
- **Email**: Resend (PDF attachments)
- **PDF**: ReportLab (professional layout with company logo)
- **Brand Colors**: #00A08C, #47D2A7, #008F7A

## Implemented
- [x] Auth (register, login, forgot-password, reset-password)
- [x] Clients CRUD
- [x] Products CRUD (edit, duplicate)
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
- [x] **Advanced Quotes page**: Product catalog quick-add, multi-line items, status badges (En attente/Envoyée/Acceptée/Refusée/Convertie), filter/sort, PDF download, email sending (Resend), convert to invoice
- [x] **Advanced Invoices page**: Product catalog quick-add, multi-line items, status badges (Brouillon/Envoyée/Payée/En retard), filter/sort, PDF download, email sending (Resend)
- [x] PDF generation with company logo, client info, item table, taxes, totals
- [x] Email sending via Resend with PDF attachment
- [x] Quote status management (PUT /api/quotes/{id}/status)

## Backlog
### P1
- Stripe subscription ($15/mois CAD, 14 jours trial, gussdub@gmail.com exempt)
- Expense receipt file upload (drag & drop)

### P2
- Employee expense approval workflow
- Edit existing quotes/invoices from the UI

### P3
- UI/UX polish
- Custom domain deployment (facturepro.ca)

## Key Files
- `/app/backend/server.py` - Backend (pymongo sync, ReportLab, Resend)
- `/app/frontend/src/App.js` - Router
- `/app/frontend/src/config.js` - Config
- `/app/frontend/src/context/AuthContext.js` - Auth
- `/app/frontend/src/components/` - Layout, FactureProLogo, etc.
- `/app/frontend/src/pages/QuotesPage.js` - Advanced quotes page
- `/app/frontend/src/pages/InvoicesPage.js` - Advanced invoices page
- `/app/DEPLOYMENT_GUIDE.md` - Render deployment guide

## Key API Endpoints
- POST /api/auth/login, /api/auth/register
- GET/POST/PUT/DELETE /api/quotes, /api/invoices, /api/clients, /api/products
- PUT /api/quotes/{id}/status, PUT /api/invoices/{id}/status
- GET /api/quotes/{id}/pdf, GET /api/invoices/{id}/pdf
- POST /api/quotes/{id}/send, POST /api/invoices/{id}/send
- POST /api/quotes/{id}/convert
- POST /api/upload, GET /api/files/{id}
