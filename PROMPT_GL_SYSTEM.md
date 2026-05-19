# CLAUDE CODE PROMPT — SAP Express GL System

## PROJECT CONTEXT

Django ERP untuk perusahaan logistik SAP Express.
Fokus: Revenue Cycle (Shipment → Invoice → Payment).

**MASALAH:** Project belum punya General Ledger System dan Financial Statements.
Harus diimplementasi sesuai teori Ch.16 General Ledger and Reporting System.

**Target flow:**
```
Shipment → Invoice → Payment
  → AUTO-CREATE Journal Entry
  → Post to General Ledger
  → Generate Trial Balance
  → Generate Income Statement + Balance Sheet
```

---

## BAGIAN 1 — Buat App Baru

```bash
python manage.py startapp general_ledger
```

Tambahkan `'general_ledger'` ke `INSTALLED_APPS` di `settings.py`.

---

## BAGIAN 2 — Models (`general_ledger/models.py`)

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
    """Chart of Account — sesuai teori Meeting 11."""
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
    """Journal Entry — setiap transaksi keuangan dicatat di sini."""
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
    """Detail line per journal entry (double-entry bookkeeping)."""
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
    """
    General Ledger — summary balance per account.
    Di-update setiap kali JournalEntry di-post.
    """
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

Setelah buat file ini:
```bash
python manage.py makemigrations general_ledger
python manage.py migrate
```

---

## BAGIAN 3 — Seed Chart of Account

Buat file: `general_ledger/management/__init__.py` (file kosong)
Buat file: `general_ledger/management/commands/__init__.py` (file kosong)
Buat file: `general_ledger/management/commands/seed_coa.py`

```python
from django.core.management.base import BaseCommand
from general_ledger.models import ChartOfAccount, GeneralLedger

COA_DATA = [
    # Assets
    ('1100', 'Cash & Bank',             'ASSET',     'DEBIT'),
    ('1200', 'Accounts Receivable',     'ASSET',     'DEBIT'),
    ('1300', 'Prepaid Expenses',        'ASSET',     'DEBIT'),
    # Liabilities
    ('2100', 'PPN Payable',             'LIABILITY', 'CREDIT'),
    ('2200', 'Accrued Liabilities',     'LIABILITY', 'CREDIT'),
    # Equity
    ('3100', 'Owner Equity',            'EQUITY',    'CREDIT'),
    ('3200', 'Retained Earnings',       'EQUITY',    'CREDIT'),
    # Revenue
    ('4000', 'Service Revenue',         'REVENUE',   'CREDIT'),
    ('4100', 'Revenue - Regular',       'REVENUE',   'CREDIT'),
    ('4200', 'Revenue - Express',       'REVENUE',   'CREDIT'),
    ('4300', 'Revenue - Same Day',      'REVENUE',   'CREDIT'),
    ('4400', 'Revenue - Cargo',         'REVENUE',   'CREDIT'),
    # Expenses
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

Jalankan:
```bash
python manage.py seed_coa
```

---

## BAGIAN 4 — Auto Journal Entry di `billing/models.py`

Di class `Payment`, tambahkan method `_create_journal_entry()` dan panggil di dalam `save()`.

**Temukan baris ini di `Payment.save()`:**
```python
        invoice.save()
```

**SETELAH baris itu, tambahkan:**
```python
        # === AUTO-CREATE JOURNAL ENTRY ===
        self._create_journal_entry()
```

**Lalu tambahkan method baru di class Payment (setelah method save):**
```python
    def _create_journal_entry(self):
        """
        Saat payment dikonfirmasi, buat double-entry journal:
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
            # Update GL balances
            gl_cash, _ = GeneralLedger.objects.get_or_create(account=cash_account)
            gl_cash.debit_total += self.amount_paid
            gl_cash.save()

            gl_ar, _ = GeneralLedger.objects.get_or_create(account=ar_account)
            gl_ar.credit_total += self.amount_paid
            gl_ar.save()

        except Exception as e:
            # Jangan break payment kalau GL belum di-setup
            pass
```

---

## BAGIAN 5 — Auto GL Entry saat Generate Invoice

Di `billing/views.py`, cari view yang membuat Invoice (kemungkinan namanya `generate_invoice` atau `create_invoice`).

**SETELAH baris `invoice.save()`, tambahkan block ini:**

```python
            # === CREATE JOURNAL ENTRY saat Invoice dibuat ===
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
                # Dr Accounts Receivable
                JournalEntryLine.objects.create(
                    journal_entry=entry, account=ar_acc,
                    debit_amount=invoice.total_amount, credit_amount=0,
                )
                # Cr Service Revenue
                JournalEntryLine.objects.create(
                    journal_entry=entry, account=rev_acc,
                    debit_amount=0, credit_amount=invoice.subtotal,
                )
                # Cr PPN Payable
                JournalEntryLine.objects.create(
                    journal_entry=entry, account=ppn_acc,
                    debit_amount=0, credit_amount=invoice.ppn_amount,
                )
                # Update GL balances
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
```

---

## BAGIAN 6 — Tambah 4 Views di `reports/views.py`

Tambahkan import ini di bagian atas file (kalau belum ada):
```python
from decimal import Decimal
```

Lalu tambahkan 4 view baru di bawah `revenue_report`:

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
    from shipments.models import Shipment
    from django.db.models import Sum

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

    gross_revenue = shipments.aggregate(t=Sum('shipping_cost'))['t'] or 0
    ppn_collected = shipments.aggregate(t=Sum('ppn_amount'))['t'] or 0

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

---

## BAGIAN 7 — Update `reports/urls.py`

Ganti seluruh isi file dengan:

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

---

## BAGIAN 8 — Update Sidebar di `base.html`

Cari bagian nav Reports, tambahkan 4 link baru setelah link Revenue Report yang sudah ada:

```html
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
```

---

## BAGIAN 9 — Buat 4 Template HTML

Buat file-file ini di `reports/templates/reports/`. Setiap template harus:
- Extends `base.html`
- Ada print button dengan `onclick="window.print()"`
- Ada `@media print` CSS di `<style>` tag yang hide `#sidebar`, `header`, `.no-print`, `.btn`
- Ada print-only header: Nama perusahaan (SAP Express Logistik), Judul laporan, Tanggal
- Format Rupiah menggunakan filter `rupiah` yang sudah ada
- Color scheme navy `#0f2a4a` + orange `#f97316`

### A. `trial_balance.html`

Tampilkan:
- Tabel dengan kolom: No. Akun | Nama Akun | Tipe | Debit | Kredit
- Footer row BOLD: Total | | | total_debit | total_credit
- Badge status: BALANCED ✓ (hijau) atau NOT BALANCED ✗ (merah)

### B. `income_statement.html`

Format akuntansi resmi:
```
PENDAPATAN
  [loop revenue_gl]  account_name ............. balance
  ──────────────────────────────────────────────────────
  Total Pendapatan                              total_revenue

BEBAN OPERASIONAL
  [loop expense_gl]  account_name ............. balance
  ──────────────────────────────────────────────────────
  Total Beban                                   total_expense

══════════════════════════════════════════════════════════
LABA BERSIH (NET INCOME)                        net_income
══════════════════════════════════════════════════════════
```

Filter tanggal (start_date, end_date) di atas tabel.

### C. `balance_sheet.html`

Format 2 kolom:
- Kolom kiri: ASET (loop asset_gl + total_assets)
- Kolom kanan: KEWAJIBAN & EKUITAS (loop liability_gl + equity_gl + net_income + total_equity + total_liabilities)
- Footer: Persamaan Akuntansi: Total Aset = Total Kewajiban + Ekuitas — status BALANCED atau NOT BALANCED
- Tampilkan `report_date` di header

### D. `journal_entries.html`

- Tabel: No. JE | Tanggal | Deskripsi | Referensi | Total Debit | Total Kredit | Status
- Setiap baris bisa di-expand (toggle) untuk lihat detail lines
- Detail: Account Code | Account Name | Debit | Credit
- Pagination di bawah

---

## BAGIAN 10 — GL Admin (`general_ledger/admin.py`)

```python
from django.contrib import admin
from .models import ChartOfAccount, JournalEntry, JournalEntryLine, GeneralLedger


class JournalEntryLineInline(admin.TabularInline):
    model  = JournalEntryLine
    extra  = 2


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

---

## CHECKLIST — Urutan Pengerjaan

- [ ] 1. `python manage.py startapp general_ledger`
- [ ] 2. Tambah `'general_ledger'` ke `INSTALLED_APPS`
- [ ] 3. Buat `general_ledger/models.py` (isi dari Bagian 2)
- [ ] 4. `python manage.py makemigrations && python manage.py migrate`
- [ ] 5. Buat folder `management/commands/` + file `seed_coa.py`
- [ ] 6. `python manage.py seed_coa`
- [ ] 7. Edit `billing/models.py` — tambah `_create_journal_entry()` di class Payment
- [ ] 8. Edit `billing/views.py` — tambah GL entry saat generate invoice
- [ ] 9. Edit `reports/views.py` — tambah 4 view baru
- [ ] 10. Edit `reports/urls.py` — tambah 4 URL
- [ ] 11. Edit `base.html` sidebar — tambah 4 nav link
- [ ] 12. Buat 4 template HTML (`trial_balance`, `income_statement`, `balance_sheet`, `journal_entries`)
- [ ] 13. Buat `general_ledger/admin.py`
- [ ] 14. Test end-to-end:
  - Buat 1 shipment baru
  - Generate invoice → cek Journal Entry terbuat (Dr AR, Cr Revenue, Cr PPN)
  - Confirm payment → cek Journal Entry terbaru (Dr Cash, Cr AR)
  - Buka Trial Balance → pastikan balanced
  - Buka Income Statement → pastikan ada revenue
  - Buka Balance Sheet → pastikan Assets = Liabilities + Equity

---

## CATATAN PENTING

1. **Circular import** — semua import `general_ledger` harus di dalam function body, bukan di top-level `billing/models.py`
2. **try/except** di `_create_journal_entry()` wajib ada — payment tidak boleh gagal karena GL error
3. **Filter Rupiah** — gunakan custom filter yang sudah ada di project (`|rupiah`)
4. **Print CSS** — setiap template report wajib punya `@media print { #sidebar, header, .no-print { display: none !important; } }`
5. **Dummy data existing** — GL balance untuk data lama tidak otomatis ter-update. Untuk demo, buat transaksi baru setelah GL di-setup
