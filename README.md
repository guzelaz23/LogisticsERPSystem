# SAP Express — Logistics ERP Solution

A web-based **Accounting Information System** built for logistics companies. SAP Express manages the full operational and financial cycle, from shipment tracking to automated double-entry bookkeeping, with zero manual journal entries required.

**Live Demo:** [guzelaz23.pythonanywhere.com](https://guzelaz23.pythonanywhere.com)

---

## Team

| Name | Student ID |
|------|------------|
| Fatwa Putri Jingga | 012202400051 |
| Ryantinisa Guzelazkia | 0122024000106 |
| Syakira Lathifa Awliya | 012202400083 |

Information System 24 — President University

---

## Features

### Operational (Operator Role)
- **Customer Management** — Register and manage client records with auto-generated customer codes
- **Shipments (AWB)** — Create and track shipments with unique Air Waybill numbers; supports Regular, Express, Same Day, and Cargo services
- **Invoices** — Auto-generated from delivered shipments with 14-day due dates
- **Payments** — Record and confirm customer payments; supports Bank Transfer, Cash, and more
- **Record Expense** — Log operational and administrative costs
- **General Entries** — Full audit trail of all auto-posted journal entries

### Reports (Management Role)
- **Shipment Report** — Filter by date, service type, and status; export to CSV
- **Revenue Report** — Monthly revenue breakdown excluding PPN
- **Trial Balance** — Verify all accounts are balanced
- **Income Statement** — Gross Revenue → Expenses → Net Income
- **Balance Sheet** — Assets = Liabilities + Equity snapshot
- **Cash Flow** — Track cash in/out per period
- **AR Aging** — Prioritize overdue invoice follow-ups
- **Chart of Accounts** — Manage the General Ledger account structure

---

## Demo Accounts

| Role | Username | Password |
|------|----------|----------|
| Operator | `ops_user` | `ops123` |
| Management | `mgmt_user` | `mgmt123` |

---

## 🛠️ Tech Stack

- **Backend:** Python / Django
- **Frontend:** HTML, CSS, JavaScript
- **Database:** PostgreSQL
- **Deployment:** PythonAnywhere

---

## Getting Started

### Prerequisites
- Python 3.x
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/guzelaz23/LogisticsERPSystem.git
cd LogisticsERPSystem

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your settings

# Run migrations
python manage.py migrate

# Set up roles and demo accounts
python manage.py setup_roles

# Start the development server
python manage.py runserver
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Project Structure

```
LogisticsERPSystem/
├── ais_finalproject/       # Main Django project settings
├── ais_project1/           # Core app configuration
├── billing/                # Invoices, payments, and expense recording
├── customers/              # Customer management
├── general_ledger/         # Journal entries and GL logic
├── reports/                # All financial and operational reports
├── shipments/              # AWB / shipment tracking
├── templates/              # HTML templates
│   └── registration/       # Login / auth templates
├── static/images/          # Static assets
├── manage.py
├── requirements.txt
└── README.md
```

---

## How It Works

### Automated Accounting
All journal entries are posted automatically — no manual bookkeeping required.

**Invoice Generation:**
| Account | Debit | Credit |
|---------|-------|--------|
| Accounts Receivable (1200) | Invoice total (incl. PPN) | — |
| Service Revenue (4200) | — | Subtotal (excl. PPN) |
| PPN Payable (2100) | — | PPN amount (11%) |

**Payment Confirmation:**
| Account | Debit | Credit |
|---------|-------|--------|
| Cash & Bank (1100) | Amount paid | — |
| Accounts Receivable (1200) | — | Amount paid |

### Shipment Status Flow
```
PENDING → PICKUP → TRANSIT → DELIVERED
                         ↘ RETURNED (auto-cancels invoice + posts reversal entry)
```

### Shipping Cost Calculation
- **Chargeable weight** = max(actual weight, volumetric weight)
- **Volumetric weight** = (L × W × H) ÷ 5,000
- **PPN** = 11% of subtotal

---

## Chart of Accounts

| Code | Account Name | Type |
|------|-------------|------|
| 1100 | Cash & Bank | Asset |
| 1200 | Accounts Receivable | Asset |
| 1300 | Prepaid Expenses | Asset |
| 2100 | PPN Payable | Liability |
| 2200 | Accrued Liabilities | Liability |
| 3100 | Owner Equity | Equity |
| 3200 | Retained Earnings | Equity |
| 4200 | Service Revenue | Revenue |
| 5100 | Operating Expenses | Expense |
| 5200 | Administrative Expenses | Expense |

---

## 📄 License

This project was built as a final project for the Accounting Information System course at President University.
