# FacturePro - PRD (Product Requirements Document)

## Original Problem Statement
Billing software "FacturePro" for Canadian businesses (French-language). Features include:
- Authentication with JWT
- Client management (CRUD)
- Product catalog (CRUD)
- Invoice generation with Canadian tax calculations (QC: GST 5% + PST 9.975%, ON: HST 13%)
- Quote generation with conversion to invoices
- Employee tracking
- Expense tracking with status workflow
- CSV exports for invoices and expenses
- Company settings (logo, tax numbers, colors)
- Dashboard with stats
- Stripe subscription ($15/month CAD, 14-day trial) - exemption for gussdub@gmail.com
- Forgot password workflow

## Architecture
- **Frontend**: React (single App.js monolith) on port 3000
- **Backend**: FastAPI with Motor (async MongoDB driver) on port 8001
- **Database**: MongoDB (local in Emergent preview, MongoDB Atlas for production)
- **Auth**: JWT tokens (24h expiry), bcrypt password hashing

## What's Been Implemented (as of 2026-02-04)
- [x] Full authentication (register, login, forgot-password, reset-password)
- [x] Clients CRUD with all fields
- [x] Products CRUD with soft delete
- [x] Invoices CRUD with Canadian tax calculation (QC/ON)
- [x] Quotes CRUD with tax calculation + convert to invoice
- [x] Employees CRUD with soft delete
- [x] Expenses CRUD with status workflow
- [x] Company Settings (get/update/logo upload via URL)
- [x] Dashboard stats (clients, invoices, quotes, products, employees, expenses, revenue)
- [x] CSV exports for invoices and expenses
- [x] Seed data for gussdub@gmail.com account
- [x] Export page with download buttons

## Testing Status
- Backend: 40/40 tests passed (100%)
- Frontend: 95% (all flows work, export page now has buttons)

## Prioritized Backlog

### P0 (Critical)
- None currently blocking

### P1 (High Priority)
- Stripe subscription integration ($15/month CAD, 14-day trial, gussdub@gmail.com exempt)
- File uploads for logos and expense receipts (currently URL-only)

### P2 (Medium)
- Employee expense approval workflow (link expenses to invoices/reimbursements)
- Refactor App.js monolith (3000+ lines) into modular components

### P3 (Low)
- PDF export for invoices (ReportLab)
- UI/UX improvements
- Preparation for custom domain deployment (facturepro.ca)

## Key API Endpoints
All prefixed with `/api`:
- POST /api/auth/login, /api/auth/register, /api/auth/forgot-password, /api/auth/reset-password
- GET/POST/PUT/DELETE /api/clients, /api/products, /api/invoices, /api/quotes, /api/employees, /api/expenses
- PUT /api/invoices/{id}/status, /api/expenses/{id}/status
- POST /api/quotes/{id}/convert
- GET/PUT /api/settings/company
- POST /api/settings/company/upload-logo
- GET /api/dashboard/stats
- GET /api/export/invoices/csv, /api/export/expenses/csv

## DB Schema (MongoDB)
- `users`: id, email, company_name, is_active, subscription_status, trial_end_date
- `user_passwords`: user_id, hashed_password
- `clients`: id, user_id, name, email, phone, address, city, postal_code, country
- `products`: id, user_id, name, description, unit_price, unit, category, is_active
- `invoices`: id, user_id, client_id, invoice_number, issue_date, due_date, items, subtotal, gst/pst/hst amounts, total, province, status, notes
- `quotes`: id, user_id, client_id, quote_number, issue_date, valid_until, items, subtotal, gst/pst/hst amounts, total, province, status, notes
- `employees`: id, user_id, name, email, phone, employee_number, department, is_active
- `expenses`: id, user_id, employee_id, description, amount, category, expense_date, status, receipt_url, notes
- `company_settings`: id, user_id, company_name, email, phone, address, city, postal_code, country, logo_url, primary_color, secondary_color, gst_number, pst_number, hst_number
