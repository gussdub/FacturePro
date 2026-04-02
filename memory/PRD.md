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

## Architecture (Post-Refactoring)
- **Frontend**: React modular components on port 3000
  - `src/App.js` - Main router (~60 lines)
  - `src/config.js` - Shared constants (BACKEND_URL, LOGO_URL, formatCurrency)
  - `src/context/AuthContext.js` - Auth provider
  - `src/components/` - Layout, NotificationsDropdown, QuickActionCard, ForgotPasswordModal
  - `src/pages/` - Dashboard, ClientsPage, ProductsPage, InvoicesPage, QuotesPage, EmployeesPage, ExpensesPage, SettingsPage, ExportPage, LoginPage
- **Backend**: FastAPI with Motor (async MongoDB driver) on port 8001
- **Database**: MongoDB (local in Emergent preview)
- **Auth**: JWT tokens (24h expiry), bcrypt password hashing
- **Brand Colors**: Teal #00A08C (primary), #47D2A7 (lighter), #008F7A (darker)

## What's Been Implemented (as of 2026-02-04)
- [x] Full authentication (register, login, forgot-password, reset-password)
- [x] Clients CRUD with search
- [x] Products CRUD with soft delete
- [x] Invoices CRUD with Canadian tax calculation (QC/ON)
- [x] Quotes CRUD with tax calculation
- [x] Employees CRUD with soft delete
- [x] Expenses CRUD with approval workflow (pending/approved/rejected)
- [x] Company Settings (get/update/logo upload via URL)
- [x] Dashboard stats (clients, invoices, quotes, products, employees, expenses, revenue)
- [x] CSV exports for invoices and expenses
- [x] Seed data for gussdub@gmail.com account
- [x] Export page with download buttons
- [x] Brand colors (teal) and FacturePro logo integrated
- [x] **REFACTORING COMPLETE**: Monolithic App.js (3000+ lines) -> 15 modular files

## Testing Status
- Backend: 40/40 tests passed (100%)
- Frontend: 100% (all navigation, CRUD, auth, export flows validated)

## Prioritized Backlog

### P1 (High Priority)
- Stripe subscription integration ($15/month CAD, 14-day trial, gussdub@gmail.com exempt)
- File uploads for logos and expense receipts (currently URL-only)

### P2 (Medium)
- Employee expense approval workflow (link expenses to invoices/reimbursements)
- Quote-to-invoice conversion in UI
- PDF export for invoices (ReportLab)

### P3 (Low)
- UI/UX polish
- Preparation for custom domain deployment (facturepro.ca)

## Key Files Reference
- `/app/backend/server.py` - Complete backend
- `/app/frontend/src/App.js` - Router
- `/app/frontend/src/config.js` - Config constants
- `/app/frontend/src/context/AuthContext.js` - Auth
- `/app/frontend/src/components/Layout.js` - Sidebar + header
- `/app/frontend/src/pages/*.js` - All page components
