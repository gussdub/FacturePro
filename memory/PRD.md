# FacturePro - PRD

## Original Problem Statement
Billing software "FacturePro" for Canadian businesses (French-language).

## Architecture
- **Frontend**: React modular (15+ fichiers) on port 3000
- **Backend**: FastAPI + pymongo sync on port 8001
- **Database**: MongoDB Atlas
- **Storage**: Emergent Object Storage (logos, recus)
- **Email**: Resend via noreply@facturepro.ca (PDF attachments, reminders)
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
- [x] Dashboard stats + overdue tracker with reminder emails
- [x] CSV exports
- [x] SVG logo (no external URL dependency)
- [x] File upload via Emergent Object Storage
- [x] Refactored monolith into modular components
- [x] pymongo sync backend (works on Render + Emergent)
- [x] Advanced Quotes page: Product dropdown, multi-line items, status badges, filter/sort, PDF, email, convert
- [x] Advanced Invoices page: Product dropdown, multi-line items, status badges, filter/sort, PDF, email
- [x] PDF generation with company logo, proper spacing (no overlaps)
- [x] Email sending via Resend (noreply@facturepro.ca) with PDF attachment
- [x] Quote/Invoice number editable in forms
- [x] Edit existing quotes/invoices (Modifier button, pre-filled form)
- [x] Empty items by default (no blank row until product selected or manual add)
- [x] Payment tracking dashboard with overdue detection + reminder emails
- [x] Backend tax recalculation on quote PUT

## Backlog
### P1
- Stripe subscription ($15/mois CAD, 14 jours trial)
- Expense receipt file upload (drag & drop)

### P2
- Employee expense approval workflow

### P3
- UI/UX polish
- Custom domain deployment (facturepro.ca)

## Key Files
- `/app/backend/server.py` - Backend
- `/app/frontend/src/pages/QuotesPage.js` - Soumissions
- `/app/frontend/src/pages/InvoicesPage.js` - Factures
- `/app/frontend/src/pages/Dashboard.js` - Dashboard + overdue tracker

## Key API Endpoints
- POST /api/auth/login, /api/auth/register
- GET/POST/PUT/DELETE /api/quotes, /api/invoices, /api/clients, /api/products
- PUT /api/quotes/{id}/status, PUT /api/invoices/{id}/status
- GET /api/quotes/{id}/pdf, GET /api/invoices/{id}/pdf
- POST /api/quotes/{id}/send, POST /api/invoices/{id}/send
- POST /api/quotes/{id}/convert
- GET /api/dashboard/stats, GET /api/dashboard/overdue
- POST /api/invoices/{id}/remind
