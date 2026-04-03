# FacturePro - PRD

## Original Problem Statement
Billing software "FacturePro" for Canadian businesses (French-language).

## Architecture
- **Frontend**: React + Recharts on port 3000
- **Backend**: FastAPI + pymongo sync on port 8001
- **Database**: MongoDB Atlas
- **Email**: Resend via noreply@facturepro.ca
- **PDF**: ReportLab

## Implemented
- [x] Auth (register, login, forgot-password, /api/auth/me)
- [x] Clients, Products, Employees, Expenses CRUD
- [x] Invoices/Quotes with Canadian taxes, PDF, email, convert
- [x] Editable quote/invoice numbers, product dropdown, edit existing
- [x] Recurring invoices (biweekly/monthly/quarterly/annual)
- [x] Dashboard: stats, overdue tracker, reminder emails
- [x] **Expense analytics charts**: Donut by category + stacked bar by month (Recharts)
- [x] CSV import for expenses with intelligent column mapping
- [x] Company Settings with logo upload + tax numbers
- [x] CSV exports, Object Storage

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
- Dashboard: /api/dashboard/stats, /api/dashboard/overdue, /api/dashboard/expense-analytics
- PDF/Email: /api/quotes/{id}/pdf, /api/invoices/{id}/pdf, /api/quotes/{id}/send, /api/invoices/{id}/send
- Recurring: /api/invoices/{id}/recurrence, /api/invoices/process-recurring
- CSV Import: /api/expenses/import-csv, /api/expenses/import-confirm
