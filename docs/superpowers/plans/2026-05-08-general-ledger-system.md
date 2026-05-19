# General Ledger System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a full General Ledger system with auto Journal Entry creation on Invoice/Payment events, and four new financial report pages (Trial Balance, Income Statement, Balance Sheet, Journal Entries).

**Architecture:** Create a new `general_ledger` Django app with COA/JournalEntry/GL models; hook into `shipments/views.py::generate_invoice` and `billing/models.py::Payment.save` to auto-post journal entries; add four views to `reports/views.py` backed by four new HTML templates.

**Tech Stack:** Django 5.x, PostgreSQL, Tailwind CSS (existing classes), Alpine.js (for expand/collapse), existing `|rupiah` custom filter, Chart-free HTML templates.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `general_ledger/__init__.py` | Create | App package |
| `general_ledger/models.py` | Create | ChartOfAccount, JournalEntry, JournalEntryLine, GeneralLedger |
| `general_ledger/admin.py` | Create | Admin registration for all GL models |
| `general_ledger/apps.py` | Create | App config |
| `general_ledger/management/__init__.py` | Create | Package |
| `general_ledger/management/commands/__init__.py` | Create | Package |
| `general_ledger/management/commands/seed_coa.py` | Create | Seed 14 chart-of-account rows + GL rows |
| `ais_project1/settings.py` | Modify | Add `'general_ledger'` to INSTALLED_APPS |
| `billing/models.py` | Modify | Add `_create_journal_entry()` to Payment, call it in save() |
| `shipments/views.py` | Modify | Add GL entry block after `invoice.save()` in `generate_invoice` |
| `reports/views.py` | Modify | Add `trial_balance`, `income_statement`, `balance_sheet`, `journal_entries` views |
| `reports/urls.py` | Modify | Replace with 6-path urlconf |
| `ais_finalproject/templates/ais_finalproject/base.html` | Modify | Add 4 nav links after Revenue Report link |
| `reports/templates/reports/trial_balance.html` | Create | Trial Balance table |
| `reports/templates/reports/income_statement.html` | Create | Income Statement format |
| `reports/templates/reports/balance_sheet.html` | Create | Balance Sheet 2-column |
| `reports/templates/reports/journal_entries.html` | Create | Journal Entries table with expand |

---

## Task 1: Create `general_ledger` App Files

**Files:**
- Create: `general_ledger/__init__.py`
- Create: `general_ledger/apps.py`
- Modify: `ais_project1/settings.py`

- [ ] **Step 1: Create app package files**

Run from the project root:
```
python manage.py startapp general_ledger
```
This creates `general_ledger/` with `__init__.py`, `apps.py`, `models.py`, `views.py`, `admin.py`, `tests.py`.

- [ ] **Step 2: Add app to INSTALLED_APPS**

In `ais_project1/settings.py`, find the INSTALLED_APPS list and add `'general_ledger'` as the last project app:

Old (line ~47):
```python
    'reports',
]
```

New:
```python
    'reports',
    'general_ledger',
]
```

- [ ] **Step 3: Verify Django recognises the app**

```
python manage.py check
```
Expected: `System check identified no issues (0 silenced).`

---

## Task 2: Write `general_ledger/models.py`

**Files:**
- Modify: `general_ledger/models.py`

- [ ] **Step 1: Replace the default models.py content**

Overwrite `general_ledger/models.py` with:

```python
from django.db import models
from django.contrib.auth.models import User


ACCOUNT_TYPE_CHOICES = [
    ('ASSET',     'Asset'),
    ('LIABILITY', 'Liability'),
    ('EQUITY',    'Equity'),
    ('REVENUE',   'Revenue'),
    ('EXPENSE',   'Expense'),
]

NORMAL_BALANCE = [
    ('DEBIT',  'Debit'),
    ('CREDIT', 'Credit'),
]


class ChartOfAccount(models.Model):
    account_code   = models.CharField(max_length=10, unique=True)
    account_name   = models.CharField(max_length=200)
    account_type   = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    normal_balance = models.CharField(max_length=10, choices=NORMAL_BALANCE)
    is_active      = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.account_code} - {self.account_name}"

    class Meta:
        ordering = ['account_code']


class JournalEntry(models.Model):
    entry_number  = models.CharField(max_length=30, unique=True)
    entry_date    = models.DateField()
    description   = models.TextField()
    reference     = models.CharField(max_length=50, blank=True)
    created_by    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    is_posted     = models.BooleanField(default=True)

    def __str__(self):
        return self.entry_number

    @property
    def total_debit(self):
        return sum(line.debit_amount for line in self.lines.all())

    @property
    def total_credit(self):
        return sum(line.credit_amount for line in self.lines.all())

    @property
    def is_balanced(self):
        return self.total_debit == self.total_credit

    def save(self, *args, **kwargs):
        if not self.entry_number:
            from django.utils import timezone
            ym = timezone.now().strftime('%Y%m')
            last = JournalEntry.objects.filter(
                entry_number__startswith=f'JE-{ym}'
            ).order_by('-entry_number').first()
            seq = int(last.entry_number.split('-')[-1]) + 1 if last else 1
            self.entry_number = f"JE-{ym}-{seq:06d}"
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-entry_date', '-created_at']
        verbose_name_plural = 'Journal Entries'


class JournalEntryLine(models.Model):
    journal_entry  = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account        = models.ForeignKey(ChartOfAccount, on_delete=models.PROTECT)
    description    = models.CharField(max_length=200, blank=True)
    debit_amount   = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit_amount  = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.account.account_code}: D={self.debit_amount} C={self.credit_amount}"

    class Meta:
        ordering = ['id']


class GeneralLedger(models.Model):
    account      = models.OneToOneField(ChartOfAccount, on_delete=models.PROTECT)
    debit_total  = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    last_updated = models.DateTimeField(auto_now=True)

    @property
    def balance(self):
        if self.account.normal_balance == 'DEBIT':
            return self.debit_total - self.credit_total
        else:
            return self.credit_total - self.debit_total

    def __str__(self):
        return f"GL: {self.account.account_code}"

    class Meta:
        ordering = ['account__account_code']
```

---

## Task 3: Run Migrations

**Files:** (database only)

- [ ] **Step 1: Create migration file**

```
python manage.py makemigrations general_ledger
```
Expected output: `Migrations for 'general_ledger': general_ledger/migrations/0001_initial.py`

- [ ] **Step 2: Apply migration**

```
python manage.py migrate
```
Expected: migration runs without error, ends with `Applying general_ledger.0001_initial... OK`

---

## Task 4: Create `seed_coa` Management Command

**Files:**
- Create: `general_ledger/management/__init__.py`
- Create: `general_ledger/management/commands/__init__.py`
- Create: `general_ledger/management/commands/seed_coa.py`

- [ ] **Step 1: Create empty package `__init__` files**

Create `general_ledger/management/__init__.py` — empty file.
Create `general_ledger/management/commands/__init__.py` — empty file.

- [ ] **Step 2: Create `seed_coa.py`**

Create `general_ledger/management/commands/seed_coa.py`:

```python
from django.core.management.base import BaseCommand
from general_ledger.models import ChartOfAccount, GeneralLedger

COA_DATA = [
    ('1100', 'Cash & Bank',             'ASSET',     'DEBIT'),
    ('1200', 'Accounts Receivable',     'ASSET',     'DEBIT'),
    ('1300', 'Prepaid Expenses',        'ASSET',     'DEBIT'),
    ('2100', 'PPN Payable',             'LIABILITY', 'CREDIT'),
    ('2200', 'Accrued Liabilities',     'LIABILITY', 'CREDIT'),
    ('3100', 'Owner Equity',            'EQUITY',    'CREDIT'),
    ('3200', 'Retained Earnings',       'EQUITY',    'CREDIT'),
    ('4000', 'Service Revenue',         'REVENUE',   'CREDIT'),
    ('4100', 'Revenue - Regular',       'REVENUE',   'CREDIT'),
    ('4200', 'Revenue - Express',       'REVENUE',   'CREDIT'),
    ('4300', 'Revenue - Same Day',      'REVENUE',   'CREDIT'),
    ('4400', 'Revenue - Cargo',         'REVENUE',   'CREDIT'),
    ('5100', 'Operating Expenses',      'EXPENSE',   'DEBIT'),
    ('5200', 'Administrative Expenses', 'EXPENSE',   'DEBIT'),
]


class Command(BaseCommand):
    help = 'Seed Chart of Account'

    def handle(self, *args, **kwargs):
        for code, name, acc_type, normal in COA_DATA:
            coa, created = ChartOfAccount.objects.get_or_create(
                account_code=code,
                defaults={
                    'account_name':   name,
                    'account_type':   acc_type,
                    'normal_balance': normal,
                }
            )
            GeneralLedger.objects.get_or_create(account=coa)
            if created:
                self.stdout.write(f'Created: {code} - {name}')
        self.stdout.write(self.style.SUCCESS('Chart of Account seeded!'))
```

- [ ] **Step 3: Run the seed command**

```
python manage.py seed_coa
```
Expected: 14 lines "Created: XXXX - ..." then "Chart of Account seeded!"
If run a second time: only "Chart of Account seeded!" (idempotent).

---

## Task 5: Add `_create_journal_entry` to `billing/models.py`

**Files:**
- Modify: `billing/models.py`

The Payment.save() currently ends at line 83 with `invoice.save()`. We add the call AFTER that line, then add the method below save().

- [ ] **Step 1: Call `_create_journal_entry` inside `save()`**

In `billing/models.py`, find this exact block (lines 76–83):

```python
        # Auto-update invoice payment status
        invoice = self.invoice
        total_paid = sum(p.amount_paid for p in invoice.payments.all())
        if total_paid >= invoice.total_amount:
            invoice.payment_status = 'PAID'
        elif total_paid > 0:
            invoice.payment_status = 'PARTIAL'
        invoice.save()
```

Replace with:

```python
        # Auto-update invoice payment status
        invoice = self.invoice
        total_paid = sum(p.amount_paid for p in invoice.payments.all())
        if total_paid >= invoice.total_amount:
            invoice.payment_status = 'PAID'
        elif total_paid > 0:
            invoice.payment_status = 'PARTIAL'
        invoice.save()
        self._create_journal_entry()
```

- [ ] **Step 2: Add the `_create_journal_entry` method**

After the `save()` method (after line 83), add this method inside class `Payment`:

```python
    def _create_journal_entry(self):
        """
        Double-entry on payment confirmed:
        DEBIT  1100 Cash & Bank         = amount_paid
        CREDIT 1200 Accounts Receivable = amount_paid
        """
        try:
            from general_ledger.models import ChartOfAccount, JournalEntry, JournalEntryLine, GeneralLedger

            cash_account = ChartOfAccount.objects.get(account_code='1100')
            ar_account   = ChartOfAccount.objects.get(account_code='1200')

            entry = JournalEntry.objects.create(
                entry_date  = self.payment_date,
                description = f'Payment received for {self.invoice.invoice_number}',
                reference   = self.invoice.invoice_number,
                created_by  = self.confirmed_by,
            )
            JournalEntryLine.objects.create(
                journal_entry=entry, account=cash_account,
                description=f'Cash received - {self.payment_number}',
                debit_amount=self.amount_paid, credit_amount=0,
            )
            JournalEntryLine.objects.create(
                journal_entry=entry, account=ar_account,
                description=f'AR cleared - {self.invoice.invoice_number}',
                debit_amount=0, credit_amount=self.amount_paid,
            )
            gl_cash, _ = GeneralLedger.objects.get_or_create(account=cash_account)
            gl_cash.debit_total += self.amount_paid
            gl_cash.save()

            gl_ar, _ = GeneralLedger.objects.get_or_create(account=ar_account)
            gl_ar.credit_total += self.amount_paid
            gl_ar.save()
        except Exception:
            pass
```

- [ ] **Step 3: Verify the file is syntactically correct**

```
python manage.py check
```
Expected: `System check identified no issues (0 silenced).`

---

## Task 6: Add GL Entry to `shipments/views.py::generate_invoice`

**Files:**
- Modify: `shipments/views.py`

The `generate_invoice` view saves the invoice at line 83. Add GL entry block immediately after that `invoice.save()` call (before `messages.success`).

- [ ] **Step 1: Insert GL entry block after `invoice.save()`**

In `shipments/views.py`, find this block (lines 83–84):

```python
    invoice.save()
    messages.success(request, f"Invoice {invoice.invoice_number} generated for AWB {shipment.awb_number}")
```

Replace with:

```python
    invoice.save()

    try:
        from general_ledger.models import ChartOfAccount, JournalEntry, JournalEntryLine, GeneralLedger
        from django.utils import timezone

        ar_acc  = ChartOfAccount.objects.get(account_code='1200')
        rev_acc = ChartOfAccount.objects.get(account_code='4000')
        ppn_acc = ChartOfAccount.objects.get(account_code='2100')

        entry = JournalEntry.objects.create(
            entry_date  = timezone.now().date(),
            description = f'Invoice issued: {invoice.invoice_number}',
            reference   = invoice.invoice_number,
        )
        JournalEntryLine.objects.create(
            journal_entry=entry, account=ar_acc,
            debit_amount=invoice.total_amount, credit_amount=0,
        )
        JournalEntryLine.objects.create(
            journal_entry=entry, account=rev_acc,
            debit_amount=0, credit_amount=invoice.subtotal,
        )
        JournalEntryLine.objects.create(
            journal_entry=entry, account=ppn_acc,
            debit_amount=0, credit_amount=invoice.ppn_amount,
        )
        for acc, field, amount in [
            (ar_acc,  'debit_total',  invoice.total_amount),
            (rev_acc, 'credit_total', invoice.subtotal),
            (ppn_acc, 'credit_total', invoice.ppn_amount),
        ]:
            gl, _ = GeneralLedger.objects.get_or_create(account=acc)
            setattr(gl, field, getattr(gl, field) + amount)
            gl.save()
    except Exception:
        pass

    messages.success(request, f"Invoice {invoice.invoice_number} generated for AWB {shipment.awb_number}")
```

- [ ] **Step 2: Verify syntax**

```
python manage.py check
```
Expected: `System check identified no issues (0 silenced).`

---

## Task 7: Add 4 Views to `reports/views.py`

**Files:**
- Modify: `reports/views.py`

- [ ] **Step 1: Add `from decimal import Decimal` import at top**

In `reports/views.py`, after line 1 (`import csv`), add:

```python
from decimal import Decimal
```

- [ ] **Step 2: Append 4 new views at end of file (after line 122)**

Add at the very bottom of `reports/views.py`:

```python


@login_required
def trial_balance(request):
    from general_ledger.models import GeneralLedger

    gl_entries   = GeneralLedger.objects.select_related('account').filter(
        account__is_active=True
    ).order_by('account__account_code')

    total_debit  = sum(gl.debit_total  for gl in gl_entries)
    total_credit = sum(gl.credit_total for gl in gl_entries)
    is_balanced  = total_debit == total_credit

    return render(request, 'reports/trial_balance.html', {
        'gl_entries':   gl_entries,
        'total_debit':  total_debit,
        'total_credit': total_credit,
        'is_balanced':  is_balanced,
    })


@login_required
def income_statement(request):
    from general_ledger.models import GeneralLedger

    start_date = request.GET.get('start_date')
    end_date   = request.GET.get('end_date')

    revenue_gl = GeneralLedger.objects.filter(
        account__account_type='REVENUE', account__is_active=True
    ).select_related('account')

    expense_gl = GeneralLedger.objects.filter(
        account__account_type='EXPENSE', account__is_active=True
    ).select_related('account')

    total_revenue = sum(gl.balance for gl in revenue_gl)
    total_expense = sum(gl.balance for gl in expense_gl)
    net_income    = total_revenue - total_expense

    shipments = Shipment.objects.filter(status='DELIVERED')
    if start_date:
        shipments = shipments.filter(created_at__date__gte=start_date)
    if end_date:
        shipments = shipments.filter(created_at__date__lte=end_date)

    from django.db.models import Sum as DSum
    gross_revenue = shipments.aggregate(t=DSum('shipping_cost'))['t'] or Decimal('0')
    ppn_collected = shipments.aggregate(t=DSum('ppn_amount'))['t'] or Decimal('0')

    return render(request, 'reports/income_statement.html', {
        'start_date':    start_date,
        'end_date':      end_date,
        'revenue_gl':    revenue_gl,
        'expense_gl':    expense_gl,
        'total_revenue': total_revenue,
        'total_expense': total_expense,
        'net_income':    net_income,
        'gross_revenue': gross_revenue,
        'ppn_collected': ppn_collected,
    })


@login_required
def balance_sheet(request):
    from general_ledger.models import GeneralLedger
    from django.utils import timezone

    asset_gl     = GeneralLedger.objects.filter(account__account_type='ASSET').select_related('account')
    liability_gl = GeneralLedger.objects.filter(account__account_type='LIABILITY').select_related('account')
    equity_gl    = GeneralLedger.objects.filter(account__account_type='EQUITY').select_related('account')

    revenue_total = sum(
        gl.balance for gl in GeneralLedger.objects.filter(account__account_type='REVENUE')
    )
    expense_total = sum(
        gl.balance for gl in GeneralLedger.objects.filter(account__account_type='EXPENSE')
    )
    net_income = revenue_total - expense_total

    total_assets      = sum(gl.balance for gl in asset_gl)
    total_liabilities = sum(gl.balance for gl in liability_gl)
    total_equity      = sum(gl.balance for gl in equity_gl) + net_income
    is_balanced       = abs(total_assets - (total_liabilities + total_equity)) < 1

    return render(request, 'reports/balance_sheet.html', {
        'asset_gl':          asset_gl,
        'liability_gl':      liability_gl,
        'equity_gl':         equity_gl,
        'total_assets':      total_assets,
        'total_liabilities': total_liabilities,
        'total_equity':      total_equity,
        'net_income':        net_income,
        'is_balanced':       is_balanced,
        'report_date':       timezone.now().date(),
    })


@login_required
def journal_entries(request):
    from general_ledger.models import JournalEntry
    from django.core.paginator import Paginator

    entries   = JournalEntry.objects.prefetch_related('lines__account').order_by('-entry_date')
    paginator = Paginator(entries, 20)
    page      = request.GET.get('page')
    entries   = paginator.get_page(page)

    return render(request, 'reports/journal_entries.html', {'entries': entries})
```

- [ ] **Step 3: Verify**

```
python manage.py check
```
Expected: `System check identified no issues (0 silenced).`

---

## Task 8: Update `reports/urls.py`

**Files:**
- Modify: `reports/urls.py`

- [ ] **Step 1: Replace entire file content**

Overwrite `reports/urls.py` with:

```python
from django.urls import path
from . import views

urlpatterns = [
    path('shipments/',        views.shipment_report,  name='shipment_report'),
    path('revenue/',          views.revenue_report,   name='revenue_report'),
    path('trial-balance/',    views.trial_balance,    name='trial_balance'),
    path('income-statement/', views.income_statement, name='income_statement'),
    path('balance-sheet/',    views.balance_sheet,    name='balance_sheet'),
    path('journal-entries/',  views.journal_entries,  name='journal_entries'),
]
```

- [ ] **Step 2: Verify**

```
python manage.py check
```
Expected: `System check identified no issues (0 silenced).`

---

## Task 9: Update Sidebar in `base.html`

**Files:**
- Modify: `ais_finalproject/templates/ais_finalproject/base.html`

The Revenue Report link ends at line 162 and `{% endif %}` is at line 163. Insert the 4 new nav links between them.

- [ ] **Step 1: Find the exact insertion point**

Find this block in `base.html` (lines 159–163):

```html
            <a href="{% url 'revenue_report' %}" class="nav-link {% if 'revenue_report' in request.resolver_match.url_name %}active{% endif %}">
                <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                Revenue Report
            </a>
            {% endif %}
```

Replace with:

```html
            <a href="{% url 'revenue_report' %}" class="nav-link {% if 'revenue_report' in request.resolver_match.url_name %}active{% endif %}">
                <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 8v8m-4-5v5m-4-2v2m-2 4h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                Revenue Report
            </a>
            <a href="{% url 'trial_balance' %}" class="nav-link {% if 'trial_balance' in request.resolver_match.url_name %}active{% endif %}">
                <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3"/>
                </svg>
                Trial Balance
            </a>
            <a href="{% url 'income_statement' %}" class="nav-link {% if 'income_statement' in request.resolver_match.url_name %}active{% endif %}">
                <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                </svg>
                Income Statement
            </a>
            <a href="{% url 'balance_sheet' %}" class="nav-link {% if 'balance_sheet' in request.resolver_match.url_name %}active{% endif %}">
                <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                </svg>
                Balance Sheet
            </a>
            <a href="{% url 'journal_entries' %}" class="nav-link {% if 'journal_entries' in request.resolver_match.url_name %}active{% endif %}">
                <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"/>
                </svg>
                Journal Entries
            </a>
            {% endif %}
```

---

## Task 10: Create 4 HTML Templates

### 10A — `trial_balance.html`

**Files:**
- Create: `reports/templates/reports/trial_balance.html`

- [ ] **Step 1: Create the file**

```html
{% extends 'ais_finalproject/base.html' %}
{% load custom_filters %}
{% block title %}Trial Balance - SAP Express{% endblock %}
{% block breadcrumb %}Trial Balance{% endblock %}

{% block content %}
<style>
    @media print {
        .print-only { display: block !important; }
        .no-print   { display: none  !important; }
        #sidebar, header, .btn { display: none !important; }
        .card { box-shadow: none !important; border: 1px solid #ddd !important; }
    }
</style>

<div class="print-only" style="display:none; text-align:center; margin-bottom:20px;">
    <h2 style="font-size:20px; font-weight:800; margin:0 0 4px; color:#0f2a4a;">SAP Express Logistik</h2>
    <h3 style="font-size:15px; font-weight:600; margin:0 0 6px;">Trial Balance</h3>
    <p style="font-size:11px; color:#888; margin:2px 0;">Generated: {% now "d M Y, H:i" %}</p>
    <hr style="border:none; border-top:2px solid #0f2a4a; margin:14px 0 20px;">
</div>

<div class="mb-5 flex items-center justify-between no-print">
    <div>
        <h1 class="text-xl font-extrabold text-slate-800">Trial Balance</h1>
        <p class="text-sm text-slate-500 mt-0.5">Debit and credit totals per account</p>
    </div>
    <button onclick="window.print()" class="btn btn-primary no-print">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"/>
        </svg>
        Print
    </button>
</div>

<!-- Balance status badge -->
<div class="mb-4">
    {% if is_balanced %}
    <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-bold bg-emerald-100 text-emerald-700">
        ✓ BALANCED
    </span>
    {% else %}
    <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-bold bg-red-100 text-red-700">
        ✗ NOT BALANCED
    </span>
    {% endif %}
</div>

<div class="card overflow-hidden">
    <table class="data-table w-full">
        <thead>
            <tr>
                <th class="text-left">No. Akun</th>
                <th class="text-left">Nama Akun</th>
                <th class="text-left">Tipe</th>
                <th class="text-right">Debit</th>
                <th class="text-right">Kredit</th>
            </tr>
        </thead>
        <tbody>
            {% for gl in gl_entries %}
            <tr>
                <td class="font-mono text-sm">{{ gl.account.account_code }}</td>
                <td>{{ gl.account.account_name }}</td>
                <td>
                    <span class="text-xs font-semibold uppercase px-2 py-0.5 rounded
                        {% if gl.account.account_type == 'ASSET' %}bg-blue-100 text-blue-700
                        {% elif gl.account.account_type == 'LIABILITY' %}bg-orange-100 text-orange-700
                        {% elif gl.account.account_type == 'EQUITY' %}bg-purple-100 text-purple-700
                        {% elif gl.account.account_type == 'REVENUE' %}bg-emerald-100 text-emerald-700
                        {% else %}bg-red-100 text-red-700{% endif %}">
                        {{ gl.account.account_type }}
                    </span>
                </td>
                <td class="text-right font-mono">{{ gl.debit_total|rupiah }}</td>
                <td class="text-right font-mono">{{ gl.credit_total|rupiah }}</td>
            </tr>
            {% empty %}
            <tr><td colspan="5" class="text-center text-slate-400 py-8">No GL data. Run seed_coa and create transactions.</td></tr>
            {% endfor %}
        </tbody>
        <tfoot>
            <tr class="font-bold text-slate-900 border-t-2 border-slate-300">
                <td colspan="3" class="py-3 px-4">TOTAL</td>
                <td class="text-right py-3 px-4 font-mono">{{ total_debit|rupiah }}</td>
                <td class="text-right py-3 px-4 font-mono">{{ total_credit|rupiah }}</td>
            </tr>
        </tfoot>
    </table>
</div>
{% endblock %}
```

### 10B — `income_statement.html`

**Files:**
- Create: `reports/templates/reports/income_statement.html`

- [ ] **Step 1: Create the file**

```html
{% extends 'ais_finalproject/base.html' %}
{% load custom_filters %}
{% block title %}Income Statement - SAP Express{% endblock %}
{% block breadcrumb %}Income Statement{% endblock %}

{% block content %}
<style>
    @media print {
        .print-only { display: block !important; }
        .no-print   { display: none  !important; }
        #sidebar, header, .btn { display: none !important; }
        .card { box-shadow: none !important; border: 1px solid #ddd !important; }
    }
    .stmt-row { display: flex; justify-content: space-between; padding: 6px 16px; }
    .stmt-total { display: flex; justify-content: space-between; padding: 8px 16px; font-weight: 700; border-top: 1px solid #e2e8f0; background: #f8fafc; }
    .stmt-net { display: flex; justify-content: space-between; padding: 12px 16px; font-weight: 800; font-size: 1.05rem; border-top: 3px double #0f2a4a; color: #0f2a4a; }
</style>

<div class="print-only" style="display:none; text-align:center; margin-bottom:20px;">
    <h2 style="font-size:20px; font-weight:800; margin:0 0 4px; color:#0f2a4a;">SAP Express Logistik</h2>
    <h3 style="font-size:15px; font-weight:600; margin:0 0 6px;">Income Statement (Laporan Laba Rugi)</h3>
    <p style="font-size:12px; color:#555; margin:2px 0;">Period: {{ start_date|default:"All" }} — {{ end_date|default:"All" }}</p>
    <p style="font-size:11px; color:#888; margin:2px 0;">Generated: {% now "d M Y, H:i" %}</p>
    <hr style="border:none; border-top:2px solid #0f2a4a; margin:14px 0 20px;">
</div>

<div class="mb-5 flex items-center justify-between no-print">
    <div>
        <h1 class="text-xl font-extrabold text-slate-800">Income Statement</h1>
        <p class="text-sm text-slate-500 mt-0.5">Laporan Laba Rugi — SAP Express Logistik</p>
    </div>
    <button onclick="window.print()" class="btn btn-primary no-print">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"/>
        </svg>
        Print
    </button>
</div>

<!-- Date filter -->
<div class="card p-5 mb-5 no-print">
    <form method="get" class="flex flex-wrap gap-4 items-end">
        <div>
            <label class="block text-xs font-bold text-slate-500 mb-1.5 uppercase tracking-wide">Start Date</label>
            <input type="date" name="start_date" value="{{ start_date }}" class="form-input" style="width:auto">
        </div>
        <div>
            <label class="block text-xs font-bold text-slate-500 mb-1.5 uppercase tracking-wide">End Date</label>
            <input type="date" name="end_date" value="{{ end_date }}" class="form-input" style="width:auto">
        </div>
        <button type="submit" class="btn btn-primary">Filter</button>
    </form>
</div>

<div class="card overflow-hidden mb-5">
    <!-- PENDAPATAN -->
    <div class="px-4 py-3 font-bold text-sm uppercase tracking-widest text-white" style="background:#0f2a4a;">
        PENDAPATAN
    </div>
    {% for gl in revenue_gl %}
    <div class="stmt-row border-b border-slate-100">
        <span class="text-slate-700">{{ gl.account.account_name }}</span>
        <span class="font-mono text-slate-800">{{ gl.balance|rupiah }}</span>
    </div>
    {% endfor %}
    <div class="stmt-total">
        <span>Total Pendapatan</span>
        <span class="font-mono">{{ total_revenue|rupiah }}</span>
    </div>

    <!-- BEBAN -->
    <div class="px-4 py-3 mt-2 font-bold text-sm uppercase tracking-widest text-white" style="background:#f97316;">
        BEBAN OPERASIONAL
    </div>
    {% for gl in expense_gl %}
    <div class="stmt-row border-b border-slate-100">
        <span class="text-slate-700">{{ gl.account.account_name }}</span>
        <span class="font-mono text-slate-800">{{ gl.balance|rupiah }}</span>
    </div>
    {% endfor %}
    <div class="stmt-total">
        <span>Total Beban</span>
        <span class="font-mono">{{ total_expense|rupiah }}</span>
    </div>

    <!-- NET INCOME -->
    <div class="stmt-net">
        <span>LABA BERSIH (NET INCOME)</span>
        <span class="font-mono {% if net_income >= 0 %}text-emerald-700{% else %}text-red-700{% endif %}">
            {{ net_income|rupiah }}
        </span>
    </div>
</div>
{% endblock %}
```

### 10C — `balance_sheet.html`

**Files:**
- Create: `reports/templates/reports/balance_sheet.html`

- [ ] **Step 1: Create the file**

```html
{% extends 'ais_finalproject/base.html' %}
{% load custom_filters %}
{% block title %}Balance Sheet - SAP Express{% endblock %}
{% block breadcrumb %}Balance Sheet{% endblock %}

{% block content %}
<style>
    @media print {
        .print-only { display: block !important; }
        .no-print   { display: none  !important; }
        #sidebar, header, .btn { display: none !important; }
        .card { box-shadow: none !important; border: 1px solid #ddd !important; }
        .bs-grid { grid-template-columns: 1fr 1fr !important; }
    }
    .bs-section-head { padding: 10px 16px; font-weight: 700; font-size: 0.8rem; letter-spacing: .1em; text-transform: uppercase; color: white; }
    .bs-row { display: flex; justify-content: space-between; padding: 6px 16px; border-bottom: 1px solid #f1f5f9; }
    .bs-total { display: flex; justify-content: space-between; padding: 9px 16px; font-weight: 700; border-top: 2px solid #e2e8f0; background: #f8fafc; }
</style>

<div class="print-only" style="display:none; text-align:center; margin-bottom:20px;">
    <h2 style="font-size:20px; font-weight:800; margin:0 0 4px; color:#0f2a4a;">SAP Express Logistik</h2>
    <h3 style="font-size:15px; font-weight:600; margin:0 0 6px;">Balance Sheet (Neraca)</h3>
    <p style="font-size:12px; color:#555; margin:2px 0;">Per tanggal: {{ report_date }}</p>
    <p style="font-size:11px; color:#888; margin:2px 0;">Generated: {% now "d M Y, H:i" %}</p>
    <hr style="border:none; border-top:2px solid #0f2a4a; margin:14px 0 20px;">
</div>

<div class="mb-5 flex items-center justify-between no-print">
    <div>
        <h1 class="text-xl font-extrabold text-slate-800">Balance Sheet</h1>
        <p class="text-sm text-slate-500 mt-0.5">Per tanggal {{ report_date }}</p>
    </div>
    <button onclick="window.print()" class="btn btn-primary no-print">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"/>
        </svg>
        Print
    </button>
</div>

<!-- Balance equation status -->
<div class="mb-4">
    {% if is_balanced %}
    <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-bold bg-emerald-100 text-emerald-700">
        ✓ Assets = Liabilities + Equity (BALANCED)
    </span>
    {% else %}
    <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-bold bg-red-100 text-red-700">
        ✗ NOT BALANCED
    </span>
    {% endif %}
</div>

<div class="grid grid-cols-1 lg:grid-cols-2 gap-5 bs-grid">
    <!-- LEFT: ASET -->
    <div class="card overflow-hidden">
        <div class="bs-section-head" style="background:#0f2a4a;">ASET</div>
        {% for gl in asset_gl %}
        <div class="bs-row">
            <span class="text-slate-700">{{ gl.account.account_name }}</span>
            <span class="font-mono">{{ gl.balance|rupiah }}</span>
        </div>
        {% endfor %}
        <div class="bs-total">
            <span>Total Aset</span>
            <span class="font-mono">{{ total_assets|rupiah }}</span>
        </div>
    </div>

    <!-- RIGHT: KEWAJIBAN & EKUITAS -->
    <div class="card overflow-hidden">
        <div class="bs-section-head" style="background:#f97316;">KEWAJIBAN</div>
        {% for gl in liability_gl %}
        <div class="bs-row">
            <span class="text-slate-700">{{ gl.account.account_name }}</span>
            <span class="font-mono">{{ gl.balance|rupiah }}</span>
        </div>
        {% endfor %}
        <div class="bs-total">
            <span>Total Kewajiban</span>
            <span class="font-mono">{{ total_liabilities|rupiah }}</span>
        </div>

        <div class="bs-section-head mt-2" style="background:#0f2a4a;">EKUITAS</div>
        {% for gl in equity_gl %}
        <div class="bs-row">
            <span class="text-slate-700">{{ gl.account.account_name }}</span>
            <span class="font-mono">{{ gl.balance|rupiah }}</span>
        </div>
        {% endfor %}
        <div class="bs-row">
            <span class="text-slate-600 italic">Laba Bersih Periode Ini</span>
            <span class="font-mono {% if net_income >= 0 %}text-emerald-700{% else %}text-red-700{% endif %}">{{ net_income|rupiah }}</span>
        </div>
        <div class="bs-total">
            <span>Total Ekuitas</span>
            <span class="font-mono">{{ total_equity|rupiah }}</span>
        </div>
    </div>
</div>
{% endblock %}
```

### 10D — `journal_entries.html`

**Files:**
- Create: `reports/templates/reports/journal_entries.html`

- [ ] **Step 1: Create the file**

```html
{% extends 'ais_finalproject/base.html' %}
{% load custom_filters %}
{% block title %}Journal Entries - SAP Express{% endblock %}
{% block breadcrumb %}Journal Entries{% endblock %}

{% block content %}
<style>
    @media print {
        .print-only { display: block !important; }
        .no-print   { display: none  !important; }
        #sidebar, header, .btn { display: none !important; }
        .card { box-shadow: none !important; border: 1px solid #ddd !important; }
    }
</style>

<div class="print-only" style="display:none; text-align:center; margin-bottom:20px;">
    <h2 style="font-size:20px; font-weight:800; margin:0 0 4px; color:#0f2a4a;">SAP Express Logistik</h2>
    <h3 style="font-size:15px; font-weight:600; margin:0 0 6px;">Journal Entries</h3>
    <p style="font-size:11px; color:#888; margin:2px 0;">Generated: {% now "d M Y, H:i" %}</p>
    <hr style="border:none; border-top:2px solid #0f2a4a; margin:14px 0 20px;">
</div>

<div class="mb-5 flex items-center justify-between no-print">
    <div>
        <h1 class="text-xl font-extrabold text-slate-800">Journal Entries</h1>
        <p class="text-sm text-slate-500 mt-0.5">All posted accounting journal entries</p>
    </div>
    <button onclick="window.print()" class="btn btn-primary no-print">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"/>
        </svg>
        Print
    </button>
</div>

<div class="card overflow-hidden">
    <table class="data-table w-full">
        <thead>
            <tr>
                <th class="text-left w-8"></th>
                <th class="text-left">No. JE</th>
                <th class="text-left">Tanggal</th>
                <th class="text-left">Deskripsi</th>
                <th class="text-left">Referensi</th>
                <th class="text-right">Total Debit</th>
                <th class="text-right">Total Kredit</th>
                <th class="text-center">Status</th>
            </tr>
        </thead>
        <tbody>
            {% for entry in entries %}
            <tr x-data="{ open: false }" class="cursor-pointer" @click="open = !open">
                <td class="text-center text-slate-400">
                    <span x-text="open ? '▾' : '▸'"></span>
                </td>
                <td class="font-mono text-sm font-semibold" style="color:#0f2a4a;">{{ entry.entry_number }}</td>
                <td class="text-sm">{{ entry.entry_date }}</td>
                <td class="text-sm text-slate-600">{{ entry.description }}</td>
                <td class="text-sm font-mono text-slate-500">{{ entry.reference }}</td>
                <td class="text-right font-mono text-sm">{{ entry.total_debit|rupiah }}</td>
                <td class="text-right font-mono text-sm">{{ entry.total_credit|rupiah }}</td>
                <td class="text-center">
                    {% if entry.is_posted %}
                    <span class="text-xs font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">Posted</span>
                    {% else %}
                    <span class="text-xs font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-500">Draft</span>
                    {% endif %}
                </td>
            </tr>
            <!-- Expandable detail rows -->
            <tr x-data="{ open: false }" x-show="open" x-cloak class="bg-slate-50">
                <td colspan="8" class="px-8 py-0">
                    <table class="w-full text-sm mb-3 mt-2">
                        <thead>
                            <tr class="text-xs text-slate-500 uppercase tracking-wide">
                                <th class="text-left py-1">Account Code</th>
                                <th class="text-left py-1">Account Name</th>
                                <th class="text-right py-1">Debit</th>
                                <th class="text-right py-1">Credit</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for line in entry.lines.all %}
                            <tr class="border-t border-slate-200">
                                <td class="py-1 font-mono text-slate-600">{{ line.account.account_code }}</td>
                                <td class="py-1 text-slate-700">{{ line.account.account_name }}</td>
                                <td class="py-1 text-right font-mono">{% if line.debit_amount %}{{ line.debit_amount|rupiah }}{% else %}—{% endif %}</td>
                                <td class="py-1 text-right font-mono">{% if line.credit_amount %}{{ line.credit_amount|rupiah }}{% else %}—{% endif %}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </td>
            </tr>
            {% empty %}
            <tr>
                <td colspan="8" class="text-center text-slate-400 py-8">No journal entries yet. Generate an invoice or confirm a payment to create entries.</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<!-- Pagination -->
{% if entries.has_other_pages %}
<div class="mt-4 flex justify-center gap-2 no-print">
    {% if entries.has_previous %}
    <a href="?page={{ entries.previous_page_number }}" class="btn btn-ghost btn-sm">← Prev</a>
    {% endif %}
    <span class="px-3 py-1.5 text-sm text-slate-500">Page {{ entries.number }} of {{ entries.paginator.num_pages }}</span>
    {% if entries.has_next %}
    <a href="?page={{ entries.next_page_number }}" class="btn btn-ghost btn-sm">Next →</a>
    {% endif %}
</div>
{% endif %}
{% endblock %}
```

**Note on expand/collapse:** The journal_entries template uses Alpine.js (`x-data`, `x-show`, `@click`). Alpine.js is already loaded in `base.html` (confirmed by the existing project using it). Each row pair shares the same `x-data` scope — the toggle row and its detail row must use the same parent element. The current implementation uses two sibling `<tr>` elements each with `x-data="{ open: false }"` which will NOT share state. Fix: wrap each entry group in a `<tbody x-data="{ open: false }">` tag instead:

Corrected template for the tbody section:
```html
        <tbody>
            {% for entry in entries %}
            <tbody x-data="{ open: false }">
                <tr class="cursor-pointer" @click="open = !open">
                    <td class="text-center text-slate-400">
                        <span x-text="open ? '▾' : '▸'"></span>
                    </td>
                    <td class="font-mono text-sm font-semibold" style="color:#0f2a4a;">{{ entry.entry_number }}</td>
                    <td class="text-sm">{{ entry.entry_date }}</td>
                    <td class="text-sm text-slate-600">{{ entry.description }}</td>
                    <td class="text-sm font-mono text-slate-500">{{ entry.reference }}</td>
                    <td class="text-right font-mono text-sm">{{ entry.total_debit|rupiah }}</td>
                    <td class="text-right font-mono text-sm">{{ entry.total_credit|rupiah }}</td>
                    <td class="text-center">
                        {% if entry.is_posted %}
                        <span class="text-xs font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">Posted</span>
                        {% else %}
                        <span class="text-xs font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-500">Draft</span>
                        {% endif %}
                    </td>
                </tr>
                <tr x-show="open" x-cloak class="bg-slate-50">
                    <td colspan="8" class="px-8 py-0">
                        <table class="w-full text-sm mb-3 mt-2">
                            <thead>
                                <tr class="text-xs text-slate-500 uppercase tracking-wide">
                                    <th class="text-left py-1">Account Code</th>
                                    <th class="text-left py-1">Account Name</th>
                                    <th class="text-right py-1">Debit</th>
                                    <th class="text-right py-1">Credit</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for line in entry.lines.all %}
                                <tr class="border-t border-slate-200">
                                    <td class="py-1 font-mono text-slate-600">{{ line.account.account_code }}</td>
                                    <td class="py-1 text-slate-700">{{ line.account.account_name }}</td>
                                    <td class="py-1 text-right font-mono">{% if line.debit_amount %}{{ line.debit_amount|rupiah }}{% else %}—{% endif %}</td>
                                    <td class="py-1 text-right font-mono">{% if line.credit_amount %}{{ line.credit_amount|rupiah }}{% else %}—{% endif %}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </td>
                </tr>
            </tbody>
            {% empty %}
            <tr>
                <td colspan="8" class="text-center text-slate-400 py-8">No journal entries yet.</td>
            </tr>
            {% endfor %}
        </tbody>
```

Use the corrected version (nested `<tbody>` per entry) when creating the file.

---

## Task 11: Create `general_ledger/admin.py`

**Files:**
- Modify: `general_ledger/admin.py`

- [ ] **Step 1: Overwrite the default admin.py**

```python
from django.contrib import admin
from .models import ChartOfAccount, JournalEntry, JournalEntryLine, GeneralLedger


class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 2


@admin.register(ChartOfAccount)
class CoAAdmin(admin.ModelAdmin):
    list_display  = ['account_code', 'account_name', 'account_type', 'normal_balance', 'is_active']
    list_filter   = ['account_type', 'is_active']
    search_fields = ['account_code', 'account_name']


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display    = ['entry_number', 'entry_date', 'description', 'reference', 'is_posted']
    list_filter     = ['is_posted', 'entry_date']
    search_fields   = ['entry_number', 'reference']
    readonly_fields = ['entry_number', 'created_at']
    inlines         = [JournalEntryLineInline]


@admin.register(GeneralLedger)
class GLAdmin(admin.ModelAdmin):
    list_display    = ['account', 'debit_total', 'credit_total', 'last_updated']
    readonly_fields = ['last_updated']
```

- [ ] **Step 2: Final system check**

```
python manage.py check
```
Expected: `System check identified no issues (0 silenced).`

---

## Task 12: End-to-End Test

- [ ] **Step 1: Start the dev server**

```
python manage.py runserver
```

- [ ] **Step 2: Create a new shipment** — log in, go to Shipments → Add, fill the form.

- [ ] **Step 3: Generate invoice** — on the shipment detail page, click Generate Invoice.
  - Expected: Invoice created. Go to Django admin → Journal Entries → verify one entry exists with Dr AR / Cr Revenue / Cr PPN.

- [ ] **Step 4: Confirm payment** — go to Billing → Confirm Payment, confirm the invoice.
  - Expected: Go to admin → Journal Entries → verify a second entry exists with Dr Cash / Cr AR.

- [ ] **Step 5: Open Trial Balance** — navigate to `/reports/trial-balance/`
  - Expected: Table shows all 14 COA rows. Total Debit = Total Credit → BALANCED badge shown.

- [ ] **Step 6: Open Income Statement** — navigate to `/reports/income-statement/`
  - Expected: Revenue section shows Service Revenue with a balance. Net Income > 0.

- [ ] **Step 7: Open Balance Sheet** — navigate to `/reports/balance-sheet/`
  - Expected: Aset column shows AR and Cash balances. BALANCED badge shown.

- [ ] **Step 8: Open Journal Entries** — navigate to `/reports/journal-entries/`
  - Expected: Two entries listed. Click a row to expand and see the debit/credit lines.
