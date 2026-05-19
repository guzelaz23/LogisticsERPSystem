# SAP Express ERP — Reports System Design
**Date:** 2026-05-05  
**Project:** AIS Final Project — SAP Express Logistic Company (Django ERP)

---

## Problem

The current reports output only shows basic KPI dashboard cards. The system flowchart requires three complete, printable management reports: Shipment Report, Revenue Analysis Report, and Financial Statement (GL Summary).

---

## Scope

Six files change, one new file is created:

| File | Change type |
|---|---|
| `reports/views.py` | Fix 2 views, add 1 new view |
| `reports/urls.py` | Add 1 URL pattern |
| `ais_finalproject/templates/ais_finalproject/base.html` | Add sidebar link |
| `reports/templates/reports/shipment_report.html` | Full rebuild |
| `reports/templates/reports/revenue_report.html` | Major additions |
| `reports/templates/reports/financial_statement.html` | New file |
| `ais_finalproject/templatetags/custom_filters.py` | Upgrade `rupiah` filter to Decimal |

---

## Section 1 — Backend (`reports/views.py`)

### `shipment_report` view
Filter: all `Shipment` objects by `created_at__date` range.

Added context keys:
- `total_shipments`, `total_weight` (Sum weight_kg), `total_revenue` (Sum total_cost)
- `delivered_count`, `pending_count`, `transit_count`
- `service_breakdown` — `.values('service_type').annotate(count=Count('id'), total=Sum('total_cost'))`
- `daily_summary` — `.annotate(day=TruncDate('created_at')).values('day').annotate(shipments_count, total_weight, total_revenue).order_by('-day')[:30]`
- `chart_labels`, `chart_data` — JSON for Chart.js (daily shipments count)

### `revenue_report` view
Filter: `Shipment.objects.filter(status='DELIVERED')` by date range.  
Also filter `Invoice` and `Payment` by same range.

New AR context keys:
- `total_invoiced` (Sum Invoice.total_amount)
- `total_paid` (Sum Payment.amount_paid for invoices in range)
- `outstanding_ar` = total_invoiced − total_paid
- `paid_count`, `unpaid_count`, `overdue_count`
- `service_breakdown` — service type with count + total revenue

Fix monthly net revenue: annotate `net=ExpressionWrapper(Sum('total_cost') - Sum('ppn_amount'), output_field=DecimalField())` on the monthly queryset so templates never do string arithmetic.

Top customers: `shipments.values('customer__name').annotate(count=Count('id'), total=Sum('total_cost')).order_by('-total')[:10]`

### `financial_statement` view (new)
- Filter: `Shipment` (status=DELIVERED), `Invoice`, `Payment` by date range
- Income statement: `gross_revenue`, `total_ppn`, `net_revenue`
- AR: `total_invoiced`, `total_collected`, `outstanding_ar`
- 4-row GL entries list (hardcoded account structure, values from aggregates)
- Balance: `total_assets`, `total_liabilities`, `total_equity`
- Invoice counts by status

---

## Section 2 — URLs (`reports/urls.py`)

```python
path('financial-statement/', views.financial_statement, name='financial_statement'),
```

---

## Section 3 — Sidebar (`base.html`)

Add inside the existing Reports `{% if %}` block:

```html
<a href="{% url 'financial_statement' %}" class="nav-link {% if request.resolver_match.url_name == 'financial_statement' %}active{% endif %}">
    <!-- document icon -->
    Financial Statement
</a>
```

---

## Section 4 — Templates

### Design constraints (all 3 templates)
- Extend `base.html`
- Font: Plus Jakarta Sans (body), JetBrains Mono (numbers)
- Colors: navy `#0f2a4a`, orange `#f97316`
- Every table has a totals row (bold)
- Empty state shown when queryset is empty
- `@media print`: hide `#sidebar`, `header`, `footer`, `.no-print`; margin-left reset; box-shadows removed
- Report header block: company name + logo, report title, period, generated date

### `shipment_report.html`
Sections:
1. Report header
2. Date filter bar + Print button
3. 4 KPI cards: Total Shipments | Delivered | In Transit | Pending
4. **Batch Summary** table — Date / Shipments / Total Weight / Total Revenue (daily_summary)
5. **Service Breakdown** table — Service / Count / Revenue / % of Total
6. **Shipment Tracking Status** table — AWB / Customer / Route / Service / Weight / Cost / Status badge

### `revenue_report.html`
Sections:
1. Report header
2. Date filter bar + Print button
3. 4 KPI cards: Gross Revenue | PPN Collected | Net Revenue | Outstanding AR
4. **AR Summary** box — Paid / Unpaid / Overdue amounts
5. Revenue Trend line chart (monthly)
6. Service Type doughnut chart + breakdown table side-by-side
7. **Monthly Breakdown** table — Month / Shipments / Gross / PPN / Net / AR Collected
8. **Top Customers** table — Customer / AWB Count / Total Revenue / Payment Status

### `financial_statement.html` (new)
Sections:
1. Formal report header block (company + period + generated date)
2. Date filter bar + Print button
3. **Income Statement** box — Gross Revenue, PPN (11%), Net Revenue
4. **AR Summary** box — Total Invoiced, Collected, Outstanding; invoice counts
5. **General Ledger Summary** table — Account Code / Name / Debit / Credit / Type + totals row
6. **Balance Summary** table — Total Assets / Total Liabilities / Total Equity
7. Print footer — system name, print date, signature placeholders

---

## Key decisions

- Monthly net revenue is computed **server-side** (not in template) to avoid broken string arithmetic
- GL entries are **computed from aggregates** at view time (not stored in a separate GL model) — appropriate for AIS project scope
- Top customers query runs on the shipment queryset (not invoice) for consistency with the report period filter
- `rupiah` filter upgraded to use `Decimal` for precision with large amounts
