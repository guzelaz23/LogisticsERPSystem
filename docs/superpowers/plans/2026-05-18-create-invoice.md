# Create Invoice UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/invoices/create/` page where FINANCE users can select an eligible shipment and generate an invoice with auto-filled amounts.

**Architecture:** Single-page form (Approach A). Django form handles validation; Alpine.js handles live preview client-side using inline JSON. `Invoice.save()` triggers `_create_journal_entry()` automatically — no extra GL code needed here.

**Tech Stack:** Django 4.x, Tailwind CSS, Alpine.js, `group_required` decorator from `ais_finalproject.utils`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `billing/forms.py` | Modify | Add `InvoiceForm` with shipment dropdown + due_date + notes |
| `billing/views.py` | Modify | Add `invoice_create` view |
| `billing/urls.py` | Modify | Add `invoices/create/` route |
| `billing/templates/billing/invoice_create.html` | Create | Two-column form + Alpine.js preview panel |
| `billing/tests.py` | Modify | Tests for form and view |

---

## Task 1: InvoiceForm

**Files:**
- Modify: `billing/forms.py`
- Modify: `billing/tests.py`

- [ ] **Step 1: Write failing tests for InvoiceForm**

Add to `billing/tests.py`:

```python
from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from decimal import Decimal
import datetime
from customers.models import Customer
from shipments.models import Shipment
from billing.models import Invoice
from billing.forms import InvoiceForm


def make_customer():
    return Customer.objects.create(
        name='PT Test', phone='08123456789', address='Jl. Test No. 1', city='Jakarta',
    )


def make_shipment(customer, awb, status='PICKUP'):
    return Shipment.objects.create(
        awb_number=awb,
        customer=customer,
        sender_name='Pengirim', sender_phone='08111', sender_address='Jl. A',
        origin_city='Jakarta',
        recipient_name='Penerima', recipient_phone='08222', recipient_address='Jl. B',
        destination_city='Surabaya',
        service_type='REG',
        weight_kg=Decimal('2.0'),
        shipping_cost=Decimal('16000'),
        ppn_amount=Decimal('1760'),
        total_cost=Decimal('17760'),
        status=status,
        input_by=User.objects.filter(username='finance_test').first(),
    )


class InvoiceFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('finance_test', password='pass')
        self.customer = make_customer()
        self.eligible = make_shipment(self.customer, 'AWB-001', status='PICKUP')
        self.pending  = make_shipment(self.customer, 'AWB-002', status='PENDING')

    def test_pending_shipment_excluded(self):
        form = InvoiceForm()
        qs = form.fields['shipment'].queryset
        self.assertNotIn(self.pending, qs)

    def test_eligible_shipment_included(self):
        form = InvoiceForm()
        qs = form.fields['shipment'].queryset
        self.assertIn(self.eligible, qs)

    def test_invoiced_shipment_excluded(self):
        Invoice.objects.create(
            shipment=self.eligible, customer=self.customer,
            subtotal=Decimal('16000'), ppn_rate=Decimal('11.00'),
            ppn_amount=Decimal('1760'), total_amount=Decimal('17760'),
            due_date=datetime.date.today(), issued_by=self.user,
        )
        form = InvoiceForm()
        qs = form.fields['shipment'].queryset
        self.assertNotIn(self.eligible, qs)

    def test_valid_form(self):
        form = InvoiceForm(data={
            'shipment': self.eligible.pk,
            'due_date': (datetime.date.today() + datetime.timedelta(days=14)).isoformat(),
            'notes': '',
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_missing_shipment_invalid(self):
        form = InvoiceForm(data={
            'shipment': '',
            'due_date': datetime.date.today().isoformat(),
            'notes': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('shipment', form.errors)
```

- [ ] **Step 2: Run tests to confirm they fail**

```
python manage.py test billing.tests.InvoiceFormTest -v 2
```

Expected: `ImportError: cannot import name 'InvoiceForm'`

- [ ] **Step 3: Add InvoiceForm to billing/forms.py**

Add after the existing `PaymentForm` class:

```python
class InvoiceForm(forms.Form):
    INPUT_CLASS = 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500'

    shipment = forms.ModelChoiceField(
        queryset=None,
        empty_label='— Select a shipment —',
        widget=forms.Select(attrs={
            'class': INPUT_CLASS,
            'x-model': 'selectedId',
            '@change': 'updatePreview()',
        }),
    )
    due_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': INPUT_CLASS}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from shipments.models import Shipment
        eligible = (
            Shipment.objects
            .exclude(status='PENDING')
            .filter(invoice__isnull=True)
            .select_related('customer')
            .order_by('-created_at')
        )
        self.fields['shipment'].queryset = eligible
        self.fields['shipment'].label_from_instance = (
            lambda s: f"{s.awb_number} — {s.customer.name} — {s.get_status_display()}"
        )
```

- [ ] **Step 4: Run tests — expect all pass**

```
python manage.py test billing.tests.InvoiceFormTest -v 2
```

Expected: `5 tests, 0 failures`

---

## Task 2: invoice_create view

**Files:**
- Modify: `billing/views.py`
- Modify: `billing/tests.py`

- [ ] **Step 1: Write failing view tests**

Add to `billing/tests.py`:

```python
class InvoiceCreateViewTest(TestCase):
    def setUp(self):
        finance_group = Group.objects.create(name='FINANCE')
        self.finance_user = User.objects.create_user('finance_view', password='pass')
        self.finance_user.groups.add(finance_group)
        self.other_user = User.objects.create_user('other_view', password='pass')
        self.customer = make_customer()
        self.shipment = make_shipment(self.customer, 'AWB-VIEW-001')

    def test_unauthenticated_redirects(self):
        response = self.client.get(reverse('invoice_create'))
        self.assertEqual(response.status_code, 302)

    def test_non_finance_gets_403(self):
        self.client.login(username='other_view', password='pass')
        response = self.client.get(reverse('invoice_create'))
        self.assertEqual(response.status_code, 403)

    def test_finance_gets_200(self):
        self.client.login(username='finance_view', password='pass')
        response = self.client.get(reverse('invoice_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'billing/invoice_create.html')

    def test_context_has_shipments_data_json(self):
        self.client.login(username='finance_view', password='pass')
        response = self.client.get(reverse('invoice_create'))
        self.assertIn('shipments_data', response.context)
        import json
        data = json.loads(response.context['shipments_data'])
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['awb'], 'AWB-VIEW-001')

    def test_post_creates_invoice(self):
        self.client.login(username='finance_view', password='pass')
        self.client.post(reverse('invoice_create'), {
            'shipment': self.shipment.pk,
            'due_date': (datetime.date.today() + datetime.timedelta(days=14)).isoformat(),
            'notes': 'created via test',
        })
        self.assertEqual(Invoice.objects.count(), 1)
        inv = Invoice.objects.first()
        self.assertEqual(inv.subtotal, Decimal('16000'))
        self.assertEqual(inv.ppn_amount, Decimal('1760'))
        self.assertEqual(inv.total_amount, Decimal('17760'))
        self.assertEqual(inv.customer, self.customer)
        self.assertEqual(inv.issued_by, self.finance_user)
        self.assertEqual(inv.notes, 'created via test')

    def test_post_redirects_to_invoice_detail(self):
        self.client.login(username='finance_view', password='pass')
        response = self.client.post(reverse('invoice_create'), {
            'shipment': self.shipment.pk,
            'due_date': (datetime.date.today() + datetime.timedelta(days=14)).isoformat(),
            'notes': '',
        })
        inv = Invoice.objects.first()
        self.assertRedirects(response, reverse('invoice_detail', kwargs={'pk': inv.pk}))

    def test_post_invalid_rerenders_form(self):
        self.client.login(username='finance_view', password='pass')
        response = self.client.post(reverse('invoice_create'), {
            'shipment': '',
            'due_date': '',
            'notes': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'billing/invoice_create.html')
```

- [ ] **Step 2: Run tests to confirm they fail**

```
python manage.py test billing.tests.InvoiceCreateViewTest -v 2
```

Expected: `NoReverseMatch: Reverse for 'invoice_create' not found`

- [ ] **Step 3: Add invoice_create to billing/views.py**

At the top of `billing/views.py`, add these three lines after the existing `import csv` line:

```python
import json
from decimal import Decimal
from datetime import timedelta
```

Then find and update the forms import line (currently line 11):

```python
# Before:
from .forms import PaymentForm, ExpenseForm

# After:
from .forms import PaymentForm, ExpenseForm, InvoiceForm
```

Then add the view at the end of `billing/views.py`:

```python
@group_required('FINANCE')
def invoice_create(request):
    from shipments.models import Shipment

    eligible_qs = (
        Shipment.objects
        .exclude(status='PENDING')
        .filter(invoice__isnull=True)
        .select_related('customer')
        .order_by('-created_at')
    )

    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        if form.is_valid():
            shipment = form.cleaned_data['shipment']
            invoice = Invoice(
                shipment=shipment,
                customer=shipment.customer,
                subtotal=shipment.shipping_cost,
                ppn_rate=Decimal('11.00'),
                ppn_amount=shipment.ppn_amount,
                total_amount=shipment.total_cost,
                due_date=form.cleaned_data['due_date'],
                notes=form.cleaned_data['notes'],
                issued_by=request.user,
            )
            invoice.save()
            messages.success(request, f"Invoice {invoice.invoice_number} created successfully.")
            return redirect('invoice_detail', pk=invoice.pk)
    else:
        form = InvoiceForm(initial={'due_date': timezone.now().date() + timedelta(days=14)})

    shipments_data = json.dumps([
        {
            'id': s.pk,
            'awb': s.awb_number,
            'customer': s.customer.name,
            'service': s.get_service_type_display(),
            'shipping_cost': float(s.shipping_cost),
            'ppn_amount': float(s.ppn_amount),
            'total_cost': float(s.total_cost),
        }
        for s in eligible_qs
    ])

    return render(request, 'billing/invoice_create.html', {
        'form': form,
        'shipments_data': shipments_data,
    })
```

- [ ] **Step 4: Run tests — expect all pass**

```
python manage.py test billing.tests.InvoiceCreateViewTest -v 2
```

Expected: `7 tests, 0 failures` (some may still fail due to missing URL — that's Task 3)

---

## Task 3: URL route

**Files:**
- Modify: `billing/urls.py`

- [ ] **Step 1: Add route to billing/urls.py**

Insert `invoices/create/` **before** `invoices/<int:pk>/` to avoid slug conflict:

```python
from django.urls import path
from . import views

urlpatterns = [
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/create/', views.invoice_create, name='invoice_create'),   # ← add this
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/print/', views.invoice_print, name='invoice_print'),
    path('payment/confirm/', views.confirm_payment, name='confirm_payment'),
    path('payment/confirm/<int:invoice_id>/', views.confirm_payment, name='confirm_payment_id'),
    path('expense/record/', views.record_expense, name='record_expense'),
]
```

- [ ] **Step 2: Run all billing tests**

```
python manage.py test billing -v 2
```

Expected: all tests pass including `InvoiceFormTest` and `InvoiceCreateViewTest`

---

## Task 4: Template

**Files:**
- Create: `billing/templates/billing/invoice_create.html`

- [ ] **Step 1: Create the template**

```html
{% extends 'ais_finalproject/base.html' %}
{% block title %}Create Invoice - SAP Express{% endblock %}
{% block breadcrumb %}Create Invoice{% endblock %}

{% block content %}
<div x-data="invoiceForm()" class="max-w-5xl mx-auto">
    <div class="flex items-center justify-between mb-6">
        <div>
            <h1 class="text-xl font-extrabold text-slate-800">Create Invoice</h1>
            <p class="text-sm text-slate-500 mt-0.5">Generate an invoice for a completed shipment</p>
        </div>
        <a href="{% url 'invoice_list' %}" class="btn btn-ghost btn-sm">← Back</a>
    </div>

    {% if messages %}
    {% for message in messages %}
    <div class="mb-4 p-3 rounded-lg {% if message.tags == 'error' %}bg-red-50 text-red-700{% else %}bg-green-50 text-green-700{% endif %} text-sm">
        {{ message }}
    </div>
    {% endfor %}
    {% endif %}

    <form method="post" class="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {% csrf_token %}

        <div class="lg:col-span-2 space-y-5">

            <!-- Step 1: Shipment -->
            <div class="card p-5">
                <h3 class="text-sm font-bold text-slate-600 mb-4 flex items-center gap-2 uppercase tracking-wider">
                    <span class="w-5 h-5 rounded-full bg-orange-500 text-white flex items-center justify-center text-xs font-bold">1</span>
                    Select Shipment
                </h3>
                <div>
                    <label class="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">
                        Shipment (AWB)
                    </label>
                    {{ form.shipment }}
                    {% if form.shipment.errors %}
                    <p class="text-red-500 text-xs mt-1">{{ form.shipment.errors.0 }}</p>
                    {% endif %}
                    <p class="text-xs text-slate-400 mt-1">Only shipments with status PICKUP or later that have no existing invoice are shown.</p>
                </div>
            </div>

            <!-- Step 2: Details -->
            <div class="card p-5">
                <h3 class="text-sm font-bold text-slate-600 mb-4 flex items-center gap-2 uppercase tracking-wider">
                    <span class="w-5 h-5 rounded-full bg-orange-500 text-white flex items-center justify-center text-xs font-bold">2</span>
                    Invoice Details
                </h3>
                <div class="space-y-4">
                    <div>
                        <label class="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Due Date</label>
                        {{ form.due_date }}
                        {% if form.due_date.errors %}
                        <p class="text-red-500 text-xs mt-1">{{ form.due_date.errors.0 }}</p>
                        {% endif %}
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">Notes (Optional)</label>
                        {{ form.notes }}
                    </div>
                </div>
            </div>

        </div>

        <!-- Preview Panel -->
        <div>
            <div class="sticky top-20 rounded-2xl overflow-hidden shadow-xl"
                 style="background:linear-gradient(160deg,#0c2340,#1a3a5c)">
                <div class="p-5 border-b border-white/10">
                    <h3 class="text-sm font-bold text-white flex items-center gap-2 uppercase tracking-wider">
                        <span class="w-5 h-5 rounded-full bg-orange-500 text-white flex items-center justify-center text-xs font-bold">3</span>
                        Invoice Preview
                    </h3>
                </div>
                <div class="p-5 space-y-3 text-sm">
                    <div class="flex justify-between text-white/60">
                        <span>Customer</span>
                        <span class="text-white/80 text-right ml-2" x-text="preview.customer || '—'"></span>
                    </div>
                    <div class="flex justify-between text-white/60">
                        <span>AWB</span>
                        <span class="font-mono text-white/80" x-text="preview.awb || '—'"></span>
                    </div>
                    <div class="flex justify-between text-white/60 pb-3 border-b border-white/10">
                        <span>Service</span>
                        <span class="text-white/80" x-text="preview.service || '—'"></span>
                    </div>
                    <div class="flex justify-between text-white/60">
                        <span>Subtotal</span>
                        <span class="font-mono text-white/80" x-text="fmt(preview.shipping_cost)"></span>
                    </div>
                    <div class="flex justify-between text-white/60 pb-3 border-b border-white/10">
                        <span>PPN (11%)</span>
                        <span class="font-mono text-white/80" x-text="fmt(preview.ppn_amount)"></span>
                    </div>
                    <div class="flex justify-between items-center py-2">
                        <span class="text-white font-bold text-base">TOTAL</span>
                        <span class="font-mono text-orange-400 text-2xl font-bold" x-text="fmt(preview.total_cost)"></span>
                    </div>
                </div>
                <div class="p-5 pt-0">
                    <button type="submit"
                            :disabled="!selectedId"
                            :class="selectedId
                                ? 'bg-orange-500 hover:bg-orange-400 cursor-pointer'
                                : 'bg-slate-600 cursor-not-allowed opacity-50'"
                            class="w-full py-3 rounded-xl text-white font-bold text-sm transition-colors shadow-lg">
                        Generate Invoice →
                    </button>
                </div>
            </div>
        </div>

    </form>
</div>

<script>
const SHIPMENTS_DATA = {{ shipments_data|safe }};

function invoiceForm() {
    return {
        selectedId: '',
        preview: {},
        updatePreview() {
            const s = SHIPMENTS_DATA.find(s => String(s.id) === String(this.selectedId));
            this.preview = s || {};
        },
        fmt(n) {
            if (n === undefined || n === null) return '—';
            return new Intl.NumberFormat('id-ID', {
                style: 'currency', currency: 'IDR', minimumFractionDigits: 0
            }).format(n);
        },
    }
}

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('input, select, textarea').forEach(el => {
        el.classList.add('form-input');
    });
});
</script>
{% endblock %}
```

- [ ] **Step 2: Start dev server and verify manually**

```
python manage.py runserver
```

Open `http://127.0.0.1:8000/billing/invoices/create/` logged in as a FINANCE user.

Verify:
- Dropdown shows only eligible shipments (non-PENDING, no existing invoice)
- Selecting a shipment updates the preview panel in real time
- Submit button is disabled when no shipment selected
- Submitting a valid form creates the invoice and redirects to `invoice_detail`
- Success message appears on the detail page
- The created invoice now appears in `invoice_list`

- [ ] **Step 3: Run full billing test suite**

```
python manage.py test billing -v 2
```

Expected: all tests pass, 0 failures.

---

## Post-Implementation Checklist

- [ ] Verify a new invoice created via the form has a corresponding `JournalEntry` (check Django Admin → General Ledger → Journal Entries, filter by the new invoice number)
- [ ] Verify `GeneralLedger` for account 1200 (AR) shows updated `debit_total` after invoice creation
- [ ] Confirm non-FINANCE users (SALES_OPS, MANAGEMENT) see 403 when accessing `/billing/invoices/create/`
