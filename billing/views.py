import csv
import json
from decimal import Decimal
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from ais_finalproject.utils import group_required
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from .models import Invoice, Payment
from .forms import PaymentForm, ExpenseForm, InvoiceForm

@group_required('OPERATOR', 'MANAGEMENT')
def invoice_list(request):
    query         = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    start_date    = request.GET.get('start_date', '')
    end_date      = request.GET.get('end_date', '')
    export        = request.GET.get('export', '')

    Invoice.objects.filter(
        payment_status='UNPAID',
        due_date__lt=timezone.now().date(),
    ).update(payment_status='OVERDUE')

    invoices = Invoice.objects.select_related('customer', 'shipment').order_by('-created_at')
    if query:
        invoices = invoices.filter(
            Q(invoice_number__icontains=query) | Q(customer__name__icontains=query)
        )
    if status_filter:
        invoices = invoices.filter(payment_status=status_filter)
    if start_date:
        invoices = invoices.filter(created_at__date__gte=start_date)
    if end_date:
        invoices = invoices.filter(created_at__date__lte=end_date)

    if export == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="invoices.csv"'
        writer = csv.writer(response)
        writer.writerow(['Invoice No', 'Date', 'Customer', 'AWB', 'Subtotal',
                         'PPN', 'Total', 'Status', 'Due Date'])
        for inv in invoices:
            writer.writerow([
                inv.invoice_number,
                inv.created_at.strftime('%Y-%m-%d'),
                inv.customer.name,
                inv.shipment.awb_number,
                inv.subtotal,
                inv.ppn_amount,
                inv.total_amount,
                inv.payment_status,
                inv.due_date.strftime('%Y-%m-%d'),
            ])
        return response

    paginator = Paginator(invoices, 20)
    page      = request.GET.get('page')
    invoices  = paginator.get_page(page)

    return render(request, 'billing/invoice_list.html', {
        'invoices':      invoices,
        'query':         query,
        'status_filter': status_filter,
        'start_date':    start_date,
        'end_date':      end_date,
        'today':         timezone.now().date(),
    })

@group_required('OPERATOR', 'MANAGEMENT')
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related('customer', 'shipment'), pk=pk)
    payments = invoice.payments.all()
    return render(request, 'billing/invoice_detail.html', {
        'invoice': invoice,
        'payments': payments,
        'today': timezone.now().date(),
    })

@group_required('OPERATOR', 'MANAGEMENT')
def invoice_print(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related('customer', 'shipment'), pk=pk)
    return render(request, 'billing/invoice_print.html', {'invoice': invoice})

@group_required('OPERATOR')
def confirm_payment(request, invoice_id=None):
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            if payment.invoice.shipment.status == 'RETURNED':
                messages.error(request, f"Cannot record payment — shipment {payment.invoice.shipment.awb_number} has been returned and the invoice is cancelled.")
                return redirect('invoice_detail', pk=payment.invoice.pk)
            if payment.invoice.payment_status == 'CANCELLED':
                messages.error(request, f"Cannot record payment — invoice {payment.invoice.invoice_number} is cancelled.")
                return redirect('invoice_detail', pk=payment.invoice.pk)
            payment.confirmed_by = request.user
            payment.save()
            if getattr(payment, '_gl_posted', False):
                messages.success(request, f"Payment {payment.payment_number} recorded successfully!")
            else:
                messages.warning(request, f"Payment {payment.payment_number} saved, but GL journal entry failed — run 'python manage.py seed_coa' if accounts are missing.")
            return redirect('invoice_detail', pk=payment.invoice.pk)
    else:
        initial = {}
        if invoice_id:
            invoice = get_object_or_404(Invoice, pk=invoice_id)
            initial = {
                'invoice': invoice,
                'amount_paid': invoice.total_amount - sum(p.amount_paid for p in invoice.payments.all())
            }
        form = PaymentForm(initial=initial)

    payable = Invoice.objects.filter(
        payment_status__in=['UNPAID', 'PARTIAL', 'OVERDUE']
    ).select_related('customer', 'shipment').prefetch_related('payments')
    invoices_json = json.dumps({
        str(inv.pk): {
            'invoice_number': inv.invoice_number,
            'customer': inv.customer.name,
            'awb': inv.shipment.awb_number,
            'status': inv.get_payment_status_display(),
            'total_amount': float(inv.total_amount),
            'already_paid': float(sum(p.amount_paid for p in inv.payments.all())),
            'outstanding': float(inv.total_amount - sum(p.amount_paid for p in inv.payments.all())),
        }
        for inv in payable
    })
    return render(request, 'billing/confirm_payment.html', {'form': form, 'invoices_json': invoices_json})


@group_required('OPERATOR', 'MANAGEMENT')
def payment_list(request):
    from .models import PAYMENT_METHOD
    start_date = request.GET.get('start_date', '')
    end_date   = request.GET.get('end_date', '')
    method     = request.GET.get('method', '')

    payments = Payment.objects.select_related('invoice__customer').order_by('-payment_date')
    if start_date:
        payments = payments.filter(payment_date__gte=start_date)
    if end_date:
        payments = payments.filter(payment_date__lte=end_date)
    if method:
        payments = payments.filter(payment_method=method)

    total = payments.aggregate(total=Sum('amount_paid'))['total'] or 0

    paginator = Paginator(payments, 20)
    page      = request.GET.get('page')
    payments  = paginator.get_page(page)

    return render(request, 'billing/payment_list.html', {
        'payments':   payments,
        'start_date': start_date,
        'end_date':   end_date,
        'method':     method,
        'total':      total,
        'methods':    PAYMENT_METHOD,
    })


@group_required('OPERATOR')
def record_expense(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            try:
                from django.db import transaction as db_transaction
                from general_ledger.models import ChartOfAccount, JournalEntry, JournalEntryLine

                acc_code     = form.cleaned_data['account']
                amount       = form.cleaned_data['amount']
                expense_date = form.cleaned_data['expense_date']
                description  = form.cleaned_data['description']
                reference    = form.cleaned_data['reference']

                with db_transaction.atomic():
                    expense_acc = ChartOfAccount.objects.get(account_code=acc_code)
                    cash_acc    = ChartOfAccount.objects.get(account_code='1100')
                    entry = JournalEntry.objects.create(
                        entry_date  = expense_date,
                        description = description,
                        reference   = reference,
                        created_by  = request.user,
                    )
                    JournalEntryLine.objects.create(
                        journal_entry=entry, account=expense_acc,
                        description=description,
                        debit_amount=amount, credit_amount=0,
                    )
                    JournalEntryLine.objects.create(
                        journal_entry=entry, account=cash_acc,
                        description=f'Cash paid — {description}',
                        debit_amount=0, credit_amount=amount,
                    )

                messages.success(request, f"Expense recorded: {entry.entry_number}")
                return redirect('operational_journal_entries')
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Expense GL posting failed: {e}", exc_info=True)
                messages.error(request, f"Error recording expense: {e}")
    else:
        form = ExpenseForm(initial={'expense_date': timezone.now().date()})

    return render(request, 'billing/record_expense.html', {'form': form})


@group_required('OPERATOR')
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
            if getattr(invoice, '_gl_posted', False):
                messages.success(request, f"Invoice {invoice.invoice_number} created successfully.")
            else:
                messages.warning(request, f"Invoice {invoice.invoice_number} saved, but GL journal entry failed — run 'python manage.py seed_coa' if accounts are missing.")
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
