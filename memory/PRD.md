# FacturePro - PRD

## Original Problem Statement
Billing software "FacturePro" for Canadian businesses (French-language). Core requirements: comprehensive form for quotes/invoices, interactive statuses, customizable PDF generation (with company logos and tax numbers), Resend email delivery, intelligent CSV import for expenses, and a Stripe subscription system ($15/month CAD, 14-day trial) to gate premium features.

## Architecture
- **Frontend**: React + Recharts + lucide-react on port 3000
- **Backend**: FastAPI + pymongo sync on port 8001
- **Database**: MongoDB Atlas
- **Email**: Resend via noreply@facturepro.ca
- **PDF**: ReportLab
- **Payments**: Stripe via emergentintegrations library
- **Storage**: Emergent Object Storage (for logos, receipts)
- **Font**: IBM Plex Sans (Google Fonts)

## Implemented
- [x] Auth (register, login, forgot-password, /api/auth/me with subscription info)
- [x] Clients, Products, Employees, Expenses CRUD
- [x] Invoices/Quotes with Canadian taxes, PDF, email, convert
- [x] Editable quote/invoice numbers, product dropdown, edit existing
- [x] Recurring invoices (biweekly/monthly/quarterly/annual)
- [x] Dashboard: stats, overdue tracker, reminder emails
- [x] Expense analytics charts: Donut by category + stacked bar by month (Recharts)
- [x] CSV import for expenses with intelligent column mapping
- [x] Company Settings with logo upload + tax numbers
- [x] CSV exports, Object Storage
- [x] **Stripe Subscription** ($15/mois CAD, 14 jours trial, gating, checkout, payment polling)
- [x] **Trial expiry email notifications** (3 days before expiration, via Resend)
- [x] **Drag & drop receipt upload** on expenses (Object Storage)
- [x] **Employee field optional** on expenses (general expenses supported)
- [x] **UI/UX Polish (P3)**: lucide-react icons, IBM Plex Sans font, monochrome color scheme, modernized sidebar/dashboard/login/subscription

## Backlog
### P1 (Completed)
- ~~Stripe subscription~~ DONE
- ~~Drag & drop receipt upload~~ DONE

### P2 (Removed by user)
- ~~Employee expense approval workflow~~ REMOVED

### P3 (Completed)
- ~~UI/UX polish~~ DONE

## Key API Endpoints
- Auth: /api/auth/login, /api/auth/register, /api/auth/me
- CRUD: /api/quotes, /api/invoices, /api/clients, /api/products, /api/expenses, /api/employees
- Dashboard: /api/dashboard/stats, /api/dashboard/overdue, /api/dashboard/expense-analytics
- PDF/Email: /api/quotes/{id}/pdf, /api/invoices/{id}/pdf, /api/quotes/{id}/send, /api/invoices/{id}/send
- Recurring: /api/invoices/{id}/recurrence, /api/invoices/process-recurring
- CSV Import: /api/expenses/import-csv, /api/expenses/import-confirm
- Subscription: /api/subscription/current, /api/subscription/create-checkout, /api/subscription/checkout-status/{session_id}
- Notifications: /api/subscription/check-trial-expiry
- Webhook: /api/webhook/stripe
- Files: /api/upload, /api/files/{file_id}

## DB Collections
- `users`: id, email, company_name, subscription_status, trial_end_date, subscription_started_at
- `invoices` / `quotes`: id, user_id, client_id, items, total, status, invoice_number
- `expenses`: id, user_id, employee_id (optional), amount, description, category, receipt_url
- `company_settings`: user_id, company_name, email, logo_url, gst_number, pst_number
- `payment_transactions`: id, user_id, session_id, amount, currency, payment_status, metadata
- `trial_notifications`: user_id, email, type, sent_at
- `files`: id, user_id, storage_path, original_filename, content_type
