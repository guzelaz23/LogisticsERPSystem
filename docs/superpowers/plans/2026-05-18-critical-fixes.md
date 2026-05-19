# Critical Business Logic Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 critical gaps in the SAP Express shipment/billing lifecycle: enforce status transition order, add a contra-revenue account, and automatically reverse GL entries when a shipment is returned.

**Architecture:** All code changes are in `shipments/views.py` and `general_ledger/management/commands/seed_coa.py`. No new models or migrations needed. The transition guard replaces a single `if` condition in `shipment_update_status`; the GL reversal is a new helper `_handle_return_reversal` called from the same view when the status becomes RETURNED.

**Tech Stack:** Django 4.x, Python 3.x, Django ORM, Django management commands, Django TestCase

---

## File Map

| File | Change |
|---|---|
| `shipments/views.py` | Add `VALID_TRANSITIONS` dict; update `shipment_update_status`; add `_handle_return_reversal` |
| `shipments/tests.py` | New test classes: `StatusTransitionGuardTest`, `ReturnReversalTest` |
| `general_ledger/management/commands/seed_coa.py` | Add account 4900 Sales Returns & Allowances |

**Task order matters:** Complete Task 1 and Task 2 before Task 3. Task 3 depends on account 4900 existing (seeded in Task 2) and the transition guard being in place (Task 1).

---

## Task 1: Status Transition Guard (C1)

**Files:**
- Modify: `shipments/views.py` (lines 61–70, the `shipment_update_status` function)
- Test: `shipments/tests.py`

- [ ] **Step 1: Write the failing tests**

Replace the entire contents of `shipments/tests.py` with:

```python
from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.urls import reverse
from decimal import Decimal
from customers.models import Customer
from shipments.models import Shipment


def make_ops_user():
    group, _ = Group.objects.get_or_create(name='SALES_OPS')
    user = User.objects.create_user('ops_test', password='pass')
    user.groups.add(group)
    return user


def make_customer_for_test():
    return Customer.objects.create(
        name='PT Guard Test', phone='081', address='Jl. A', city='Jakarta'
    )


def make_shipment_with_status(customer, status, awb):
    return Shipment.objects.create(
        awb_number=awb,
        customer=customer,
        sender_name='S', sender_phone='1', sender_address='A',
        origin_city='Jakarta',
        recipient_name='R', recipient_phone='2', recipient_address='B',
        destination_city='Surabaya',
        service_type='REG',
        weight_kg=Decimal('1.0'),
        shipping_cost=Decimal('8000'),
        ppn_amount=Decimal('880'),
        total_cost=Decimal('8880'),
        status=status,
    )


class StatusTransitionGuardTest(TestCase):
    def setUp(self):
        self.user = make_ops_user()
        self.customer = make_customer_for_test()
        self.client.login(username='ops_test', password='pass')

    def _update(self, shipment, new_status):
        return self.client.post(
            reverse('shipment_update_status', kwargs={'pk': shipment.pk}),
            {'status': new_status},
        )

    def test_pending_to_pickup_allowed(self):
        s = make_shipment_with_status(self.customer, 'PENDING', 'AWB-G-001')
        self._update(s, 'PICKUP')
        s.refresh_from_db()
        self.assertEqual(s.status, 'PICKUP')

    def test_pickup_to_transit_allowed(self):
        s = make_shipment_with_status(self.customer, 'PICKUP', 'AWB-G-002')
        self._update(s, 'TRANSIT')
        s.refresh_from_db()
        self.assertEqual(s.status, 'TRANSIT')

    def test_transit_to_delivered_allowed(self):
        s = make_shipment_with_status(self.customer, 'TRANSIT', 'AWB-G-003')
        self._update(s, 'DELIVERED')
        s.refresh_from_db()
        self.assertEqual(s.status, 'DELIVERED')

    def test_transit_to_returned_allowed(self):
        s = make_shipment_with_status(self.customer, 'TRANSIT', 'AWB-G-004')
        self._update(s, 'RETURNED')
        s.refresh_from_db()
        self.assertEqual(s.status, 'RETURNED')

    def test_delivered_to_pending_rejected(self):
        s = make_shipment_with_status(self.customer, 'DELIVERED', 'AWB-G-005')
        self._update(s, 'PENDING')
        s.refresh_from_db()
        self.assertEqual(s.status, 'DELIVERED')

    def test_pending_to_delivered_rejected(self):
        s = make_shipment_with_status(self.customer, 'PENDING', 'AWB-G-006')
        self._update(s, 'DELIVERED')
        s.refresh_from_db()
        self.assertEqual(s.status, 'PENDING')

    def test_returned_is_terminal(self):
        s = make_shipment_with_status(self.customer, 'RETURNED', 'AWB-G-007')
        self._update(s, 'DELIVERED')
        s.refresh_from_db()
        self.assertEqual(s.status, 'RETURNED')

    def test_delivered_is_terminal(self):
        s = make_shipment_with_status(self.customer, 'DELIVERED', 'AWB-G-008')
        self._update(s, 'TRANSIT')
        s.refresh_from_db()
        self.assertEqual(s.status, 'DELIVERED')
```

- [ ] **Step 2: Run tests to verify they fail**

```
python manage.py test shipments.tests.StatusTransitionGuardTest
```

Expected: `test_delivered_to_pending_rejected`, `test_pending_to_delivered_rejected`, `test_returned_is_terminal`, and `test_delivered_is_terminal` FAIL — the current view accepts any valid choice regardless of current status.

- [ ] **Step 3: Implement the transition guard in `shipments/views.py`**

Add the `VALID_TRANSITIONS` dict and replace `shipment_update_status`. In `shipments/views.py`, replace lines 61–70 (the `@group_required('SALES_OPS')` decorator through the end of `shipment_update_status`) with:

```python
VALID_TRANSITIONS = {
    'PENDING':   {'PICKUP'},
    'PICKUP':    {'TRANSIT'},
    'TRANSIT':   {'DELIVERED', 'RETURNED'},
    'DELIVERED': set(),
    'RETURNED':  set(),
}

@group_required('SALES_OPS')
def shipment_update_status(request, pk):
    shipment = get_object_or_404(Shipment, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        allowed = VALID_TRANSITIONS.get(shipment.status, set())
        if new_status not in allowed:
            label = dict(Shipment._meta.get_field('status').choices).get(new_status, new_status)
            messages.error(
                request,
                f"Cannot change status from {shipment.get_status_display()} to {label}."
            )
            return redirect('shipment_detail', pk=pk)
        shipment.status = new_status
        shipment.save()
        messages.success(request, f"Status for {shipment.awb_number} updated to {shipment.get_status_display()}")
    return redirect('shipment_detail', pk=pk)
```

The `SERVICE_REVENUE_MAP` dict and `generate_invoice` view that follow are unchanged — do not remove them.

- [ ] **Step 4: Run tests to verify they pass**

```
python manage.py test shipments.tests.StatusTransitionGuardTest
```

Expected: 8 tests PASS.

- [ ] **Step 5: Commit**

```
git add shipments/views.py shipments/tests.py
git commit -m "fix: enforce shipment status transition order

PENDING→PICKUP→TRANSIT→DELIVERED|RETURNED only.
DELIVERED and RETURNED are terminal states.
Invalid transitions show an error message and leave status unchanged."
```

---

## Task 2: Add Contra-Revenue Account to COA (C4)

**Files:**
- Modify: `general_ledger/management/commands/seed_coa.py`

- [ ] **Step 1: Add account 4900 to `COA_DATA`**

In `general_ledger/management/commands/seed_coa.py`, add one tuple to `COA_DATA` between `4400` and `5100`:

```python
COA_DATA = [
    ('1100', 'Cash & Bank',                'ASSET',     'DEBIT'),
    ('1200', 'Accounts Receivable',        'ASSET',     'DEBIT'),
    ('1300', 'Prepaid Expenses',           'ASSET',     'DEBIT'),
    ('2100', 'PPN Payable',                'LIABILITY', 'CREDIT'),
    ('2200', 'Accrued Liabilities',        'LIABILITY', 'CREDIT'),
    ('3100', 'Owner Equity',               'EQUITY',    'CREDIT'),
    ('3200', 'Retained Earnings',          'EQUITY',    'CREDIT'),
    ('4000', 'Service Revenue',            'REVENUE',   'CREDIT'),
    ('4100', 'Revenue - Regular',          'REVENUE',   'CREDIT'),
    ('4200', 'Revenue - Express',          'REVENUE',   'CREDIT'),
    ('4300', 'Revenue - Same Day',         'REVENUE',   'CREDIT'),
    ('4400', 'Revenue - Cargo',            'REVENUE',   'CREDIT'),
    ('4900', 'Sales Returns & Allowances', 'REVENUE',   'DEBIT'),
    ('5100', 'Operating Expenses',         'EXPENSE',   'DEBIT'),
    ('5200', 'Administrative Expenses',    'EXPENSE',   'DEBIT'),
]
```

Account 4900 is a contra-revenue account: type=REVENUE, normal_balance=DEBIT (opposite of revenue). On the Income Statement it reduces total revenue.

- [ ] **Step 2: Run seed_coa**

```
python manage.py seed_coa
```

Expected output includes: `Created: 4900 - Sales Returns & Allowances`

> If you get a database connection error, fix the DB credentials in `.env` first and re-run.

- [ ] **Step 3: Commit**

```
git add general_ledger/management/commands/seed_coa.py
git commit -m "feat: add account 4900 Sales Returns & Allowances to COA

Contra-revenue account required for GL reversal when shipments are returned."
```

---

## Task 3: GL Reversal on RETURNED Status (C2 + C3)

**Depends on:** Task 1 (transition guard in place) and Task 2 (account 4900 seeded).

**Files:**
- Modify: `shipments/views.py` — add `_handle_return_reversal`, update `shipment_update_status`
- Modify: `shipments/tests.py` — append `ReturnReversalTest` class

- [ ] **Step 1: Append the failing tests to `shipments/tests.py`**

Add the following at the **end** of `shipments/tests.py` (after the `StatusTransitionGuardTest` class):

```python
import datetime
from billing.models import Invoice
from general_ledger.models import ChartOfAccount, JournalEntry, JournalEntryLine


def make_coa():
    """Create the minimum COA accounts needed for GL posting tests."""
    ChartOfAccount.objects.create(
        account_code='1200', account_name='AR',
        account_type='ASSET', normal_balance='DEBIT',
    )
    ChartOfAccount.objects.create(
        account_code='2100', account_name='PPN Payable',
        account_type='LIABILITY', normal_balance='CREDIT',
    )
    ChartOfAccount.objects.create(
        account_code='4100', account_name='Revenue - Regular',
        account_type='REVENUE', normal_balance='CREDIT',
    )
    ChartOfAccount.objects.create(
        account_code='4900', account_name='Sales Returns & Allowances',
        account_type='REVENUE', normal_balance='DEBIT',
    )


class ReturnReversalTest(TestCase):
    def setUp(self):
        self.user = make_ops_user()
        self.customer = make_customer_for_test()
        make_coa()
        self.client.login(username='ops_test', password='pass')
        # Shipment in TRANSIT — the only valid origin for RETURNED transition
        self.shipment = make_shipment_with_status(self.customer, 'TRANSIT', 'AWB-R-001')
        # Invoice linked to that shipment
        self.invoice = Invoice.objects.create(
            shipment=self.shipment,
            customer=self.customer,
            subtotal=Decimal('8000'),
            ppn_rate=Decimal('11.00'),
            ppn_amount=Decimal('880'),
            total_amount=Decimal('8880'),
            due_date=datetime.date.today(),
            issued_by=self.user,
        )

    def _return_shipment(self):
        return self.client.post(
            reverse('shipment_update_status', kwargs={'pk': self.shipment.pk}),
            {'status': 'RETURNED'},
        )

    def test_return_creates_reversal_journal_entry(self):
        je_count_before = JournalEntry.objects.count()
        self._return_shipment()
        self.assertEqual(JournalEntry.objects.count(), je_count_before + 1)

    def test_reversal_je_has_correct_lines(self):
        self._return_shipment()
        reversal_je = JournalEntry.objects.filter(reference__startswith='RET-').last()
        self.assertIsNotNone(reversal_je)
        lines = list(reversal_je.lines.all())
        self.assertEqual(len(lines), 3)
        # Dr Sales Returns 4900 = subtotal
        contra = next(l for l in lines if l.account.account_code == '4900')
        self.assertEqual(contra.debit_amount, Decimal('8000'))
        self.assertEqual(contra.credit_amount, Decimal('0'))
        # Dr PPN Payable 2100 = ppn_amount
        ppn = next(l for l in lines if l.account.account_code == '2100')
        self.assertEqual(ppn.debit_amount, Decimal('880'))
        self.assertEqual(ppn.credit_amount, Decimal('0'))
        # Cr AR 1200 = total_amount
        ar = next(l for l in lines if l.account.account_code == '1200')
        self.assertEqual(ar.debit_amount, Decimal('0'))
        self.assertEqual(ar.credit_amount, Decimal('8880'))

    def test_return_updates_invoice_notes(self):
        self._return_shipment()
        self.invoice.refresh_from_db()
        self.assertIn('RETURNED', self.invoice.notes)

    def test_return_without_invoice_creates_no_extra_je(self):
        shipment_no_inv = make_shipment_with_status(self.customer, 'TRANSIT', 'AWB-R-002')
        je_count_before = JournalEntry.objects.count()
        response = self.client.post(
            reverse('shipment_update_status', kwargs={'pk': shipment_no_inv.pk}),
            {'status': 'RETURNED'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(JournalEntry.objects.count(), je_count_before)
```

- [ ] **Step 2: Run tests to verify they fail**

```
python manage.py test shipments.tests.ReturnReversalTest
```

Expected: All 4 tests FAIL — `_handle_return_reversal` does not exist yet.

- [ ] **Step 3: Add `_handle_return_reversal` to `shipments/views.py`**

Insert the following function immediately after the closing line of `shipment_update_status` and before `SERVICE_REVENUE_MAP`:

```python
def _handle_return_reversal(shipment, user):
    from django.db import transaction as db_transaction
    from general_ledger.models import ChartOfAccount, JournalEntry, JournalEntryLine
    from django.utils import timezone
    if not hasattr(shipment, 'invoice'):
        return
    invoice = shipment.invoice
    try:
        with db_transaction.atomic():
            ar_acc     = ChartOfAccount.objects.get(account_code='1200')
            contra_acc = ChartOfAccount.objects.get(account_code='4900')
            ppn_acc    = ChartOfAccount.objects.get(account_code='2100')
            entry = JournalEntry.objects.create(
                entry_date  = timezone.now().date(),
                description = f'Return reversal: {invoice.invoice_number}',
                reference   = f'RET-{invoice.invoice_number}',
                created_by  = user,
            )
            JournalEntryLine.objects.create(
                journal_entry=entry, account=contra_acc,
                description=f'Sales return - {invoice.invoice_number}',
                debit_amount=invoice.subtotal, credit_amount=0,
            )
            JournalEntryLine.objects.create(
                journal_entry=entry, account=ppn_acc,
                description=f'PPN reversal - {invoice.invoice_number}',
                debit_amount=invoice.ppn_amount, credit_amount=0,
            )
            JournalEntryLine.objects.create(
                journal_entry=entry, account=ar_acc,
                description=f'AR cleared - {invoice.invoice_number}',
                debit_amount=0, credit_amount=invoice.total_amount,
            )
        note_line = f'\n[RETURNED on {timezone.now().date()} — GL reversal posted: {entry.entry_number}]'
        Invoice.objects.filter(pk=invoice.pk).update(notes=invoice.notes + note_line)
    except Exception as e:
        logger.error(
            f"Return reversal GL posting failed for {invoice.invoice_number}: {e}",
            exc_info=True,
        )
```

- [ ] **Step 4: Call `_handle_return_reversal` from `shipment_update_status`**

In `shipments/views.py`, update the `shipment_update_status` function to call the helper after saving. Replace the current function body (keep `VALID_TRANSITIONS` above it unchanged):

```python
@group_required('SALES_OPS')
def shipment_update_status(request, pk):
    shipment = get_object_or_404(Shipment, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        allowed = VALID_TRANSITIONS.get(shipment.status, set())
        if new_status not in allowed:
            label = dict(Shipment._meta.get_field('status').choices).get(new_status, new_status)
            messages.error(
                request,
                f"Cannot change status from {shipment.get_status_display()} to {label}."
            )
            return redirect('shipment_detail', pk=pk)
        shipment.status = new_status
        shipment.save()
        messages.success(request, f"Status for {shipment.awb_number} updated to {shipment.get_status_display()}")
        if new_status == 'RETURNED':
            _handle_return_reversal(shipment, request.user)
    return redirect('shipment_detail', pk=pk)
```

- [ ] **Step 5: Run reversal tests**

```
python manage.py test shipments.tests.ReturnReversalTest
```

Expected: 4 tests PASS.

- [ ] **Step 6: Run full test suite**

```
python manage.py test
```

Expected: All tests PASS (billing 12 + shipments 12 = 24 total). If any billing test fails, it is unrelated to this plan — investigate separately.

- [ ] **Step 7: Commit**

```
git add shipments/views.py shipments/tests.py
git commit -m "fix: post GL reversal when shipment is returned (C2/C3)

When status changes to RETURNED and an invoice exists, _handle_return_reversal
posts a balanced JE: Dr Sales Returns 4900, Dr PPN Payable 2100, Cr AR 1200.
Failure is caught and logged (never raises). Invoice notes are updated with
the JE number so the link is auditable. Shipments without an invoice are skipped."
```

---

## Self-Review Checklist

- **C1 covered?** Yes — Task 1 adds `VALID_TRANSITIONS` and replaces the loose `in choices` check.
- **C2 covered?** Yes — Task 3 updates invoice notes with reversal JE number, surfacing the return in the invoice record.
- **C3 covered?** Yes — Task 3 posts Dr 4900 / Dr 2100 / Cr 1200, reversing the revenue and AR from the original invoice JE.
- **C4 covered?** Yes — Task 2 adds account 4900 to seed_coa.
- **No migrations needed?** Confirmed — only `views.py` and `seed_coa.py` are changed.
- **GL failures silent?** No — `_handle_return_reversal` logs the error and never raises, consistent with existing GL posting pattern.
- **No placeholders?** Confirmed — all code blocks are complete and runnable.
