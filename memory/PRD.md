# FacturePro - PRD

## Original Problem Statement
Billing software "FacturePro" for Canadian businesses (French-language).

## Architecture
- **Frontend**: React modular on port 3000
- **Backend**: FastAPI + pymongo sync on port 8001
- **Database**: MongoDB Atlas
- **Storage**: Emergent Object Storage
- **Email**: Resend via noreply@facturepro.ca
- **PDF**: ReportLab

## Implemented
- [x] Auth (register, login, forgot-password, /api/auth/me)
- [x] Clients CRUD
- [x] Products CRUD (edit, duplicate)
- [x] Invoices CRUD with Canadian taxes (QC/ON)
- [x] Quotes CRUD + convert to invoice
- [x] Employees CRUD
- [x] Expenses CRUD with approval workflow
- [x] Company Settings with logo upload + tax numbers
- [x] Dashboard stats + overdue tracker + reminder emails
- [x] CSV exports
- [x] Advanced Quotes: Product dropdown, editable number, status badges, filter/sort, PDF, email, convert
- [x] Advanced Invoices: Product dropdown, editable number, status badges, filter/sort, PDF, email
- [x] Edit existing quotes/invoices (Modifier button)
- [x] Recurring invoices (biweekly/monthly/quarterly/annual, auto-send, pause/resume)
- [x] **CSV import for expenses**: Intelligent column mapping (regex-based), supports French bank exports, semicolons, accent chars, comma decimals, multiple date formats, preview with editable table, row toggle, confirm import
- [x] PDF with proper spacing, company logo, tax numbers
- [x] Profile auto-reload on refresh

## Backlog
### P1
- Stripe subscription ($15/mois CAD, 14 jours trial)

### P2
- Employee expense approval workflow
- Expense receipt file upload (drag & drop)

### P3
- UI/UX polish

## Key API Endpoints
- Auth: /api/auth/login, /api/auth/register, /api/auth/me
- CRUD: /api/quotes, /api/invoices, /api/clients, /api/products, /api/expenses, /api/employees
- Status: /api/quotes/{id}/status, /api/invoices/{id}/status
- PDF: /api/quotes/{id}/pdf, /api/invoices/{id}/pdf
- Email: /api/quotes/{id}/send, /api/invoices/{id}/send
- Convert: /api/quotes/{id}/convert
- Dashboard: /api/dashboard/stats, /api/dashboard/overdue
- Remind: /api/invoices/{id}/remind
- Recurring: /api/invoices/{id}/recurrence, /api/invoices/process-recurring
- CSV Import: /api/expenses/import-csv, /api/expenses/import-confirm
