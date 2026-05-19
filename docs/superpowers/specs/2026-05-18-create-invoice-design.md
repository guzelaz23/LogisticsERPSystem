# Create Invoice UI — Design Spec
**Date:** 2026-05-18  
**Project:** SAP Express AIS  
**Status:** Approved

---

## Problem

Finance users cannot create invoices from the web UI. The only path is Django Admin. This blocks the core billing workflow.

## Scope

Add a single-page Create Invoice form at `/invoices/create/`. No new models, no migrations.

---

## Decisions

| Decision | Choice | Reason |
|---|---|---|
| Layout | Single page with Alpine.js auto-fill | Consistent with existing shipment add form pattern |
| Eligible shipments | status != PENDING + no existing invoice | Must be at least picked up before billing |
| Permission | FINANCE only | Consistent with `confirm_payment` |
| Amounts | Read-only, auto-filled from shipment | Invoice amounts must mirror shipment costs |
| Redirect after save | `invoice_detail` of the new invoice | Natural next step (view/print) |

---

## URL

```
GET  /billing/invoices/create/       → show form
POST /billing/invoices/create/       → save invoice, redirect to invoice_detail
```

---

## Eligible Shipments Query

```python
Shipment.objects.exclude(status='PENDING').filter(invoice__isnull=True)
```

---

## Form: `InvoiceForm`

Added to `billing/forms.py`.

| Field | Type | Notes |
|---|---|---|
| `shipment` | `ModelChoiceField` | Filtered to eligible shipments; label shows AWB + customer + status |
| `due_date` | `DateField` | `type="date"` widget; initial = today + 14 days |
| `notes` | `CharField` | Optional, `Textarea` widget |

Fields NOT in the form (set in view): `customer`, `subtotal`, `ppn_rate`, `ppn_amount`, `total_amount`, `issued_by`.

---

## View: `invoice_create`

Added to `billing/views.py`.

- Decorator: `@group_required('FINANCE')`
- `GET`: render form + pass `shipments_data` as JSON for Alpine.js
- `POST`: validate form → derive amounts from `shipment` → create `Invoice` → redirect to `invoice_detail`

Amount derivation on POST:
```python
shipment = form.cleaned_data['shipment']
invoice.customer     = shipment.customer
invoice.subtotal     = shipment.shipping_cost
invoice.ppn_rate     = Decimal('11.00')
invoice.ppn_amount   = shipment.ppn_amount
invoice.total_amount = shipment.total_cost
invoice.issued_by    = request.user
```

Error handling: if `form.is_valid()` fails, re-render form with errors. No try/except needed — `Invoice.save()` and `_create_journal_entry()` already handle GL errors internally without raising.

---

## Template: `invoice_create.html`

Extends `ais_finalproject/base.html`. Two-column layout (lg:grid-cols-3) matching `shipments/add.html` pattern:

**Left (col-span-2):** Form card with shipment dropdown, due date, notes fields.

**Right (sticky):** Preview panel (dark gradient, same style as shipment add) showing:
- Customer name
- AWB number
- Service type
- Subtotal
- PPN (11%)
- **Total Amount** (highlighted in orange)

Alpine.js data: `shipments_data` JSON injected from view. Structure per item:
```json
{ "id": 1, "awb": "AWB-...", "customer": "PT X", "service": "Express (1-2 hari)",
  "shipping_cost": 150000, "ppn_amount": 16500, "total_cost": 166500 }
```
On shipment select → match by id → update preview fields instantly. If no shipment selected, preview shows dashes and submit button is disabled.

Submit button: "Generate Invoice →" (orange, full-width in preview panel).

---

## `billing/urls.py` addition

```python
path('invoices/create/', views.invoice_create, name='invoice_create'),
```

Place before `invoices/<int:pk>/` to avoid slug conflict.

---

## Out of Scope

- Editing invoice amounts manually (amounts always come from shipment)
- Bulk invoice generation
- Invoice create from shipment detail page (separate task)
- Email/notification on invoice creation
