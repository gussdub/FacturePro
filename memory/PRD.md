# FacturePro - PRD

## Original Problem Statement
Billing software "FacturePro" for Canadian businesses (French-language).

## Architecture
- **Frontend**: React modular (15+ fichiers) on port 3000
- **Backend**: FastAPI + pymongo sync on port 8001
- **Database**: MongoDB Atlas
- **Storage**: Emergent Object Storage (logos, recus)
- **Email**: Resend via noreply@facturepro.ca (PDF attachments, reminders, recurring)
- **PDF**: ReportLab (professional layout with company logo)
- **Brand Colors**: #00A08C, #47D2A7, #008F7A

## Implemented
- [x] Auth (register, login, forgot-password, reset-password, /api/auth/me)
- [x] Clients CRUD
- [x] Products CRUD (edit, duplicate)
- [x] Invoices CRUD with Canadian taxes (QC/ON)
- [x] Quotes CRUD + convert to invoice
- [x] Employees CRUD
- [x] Expenses CRUD
- [x] Company Settings with drag-and-drop logo upload + tax numbers (TPS/TVQ/TVH)
- [x] Dashboard stats + overdue tracker with reminder emails
- [x] CSV exports
- [x] SVG logo
- [x] File upload via Emergent Object Storage
- [x] Advanced Quotes: Product dropdown, editable number, status badges, filter/sort, PDF, email, convert
- [x] Advanced Invoices: Product dropdown, editable number, status badges, filter/sort, PDF, email
- [x] Edit existing quotes/invoices (Modifier button, pre-filled form)
- [x] Empty items by default
- [x] PDF generation with proper spacing (logo, client info, items)
- [x] **Recurring invoices**: Frequency (biweekly/monthly/quarterly/annual), auto-send on schedule, pause/resume, "Envoyer récurrentes" button, modify between sends
- [x] Profile auto-reload on page refresh (/api/auth/me)

## Backlog
### P1
- Stripe subscription ($15/mois CAD, 14 jours trial)
- Expense receipt file upload (drag & drop)

### P2
- Employee expense approval workflow

### P3
- UI/UX polish
- Custom domain deployment (facturepro.ca)

## Key API Endpoints
- POST /api/auth/login, /api/auth/register, GET /api/auth/me
- GET/POST/PUT/DELETE /api/quotes, /api/invoices, /api/clients, /api/products
- PUT /api/quotes/{id}/status, PUT /api/invoices/{id}/status
- GET /api/quotes/{id}/pdf, GET /api/invoices/{id}/pdf
- POST /api/quotes/{id}/send, POST /api/invoices/{id}/send
- POST /api/quotes/{id}/convert
- GET /api/dashboard/stats, GET /api/dashboard/overdue
- POST /api/invoices/{id}/remind
- PUT /api/invoices/{id}/recurrence
- POST /api/invoices/process-recurring
