import logging
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from ais_finalproject.utils import group_required

logger = logging.getLogger(__name__)
from django.core.paginator import Paginator
from django.http import JsonResponse
from .models import Shipment
from .forms import ShipmentForm
from customers.models import Customer
from billing.models import Invoice

@login_required
def shipment_list(request):
    query = request.GET.get('q', '')
    if query:
        shipments_list = Shipment.objects.filter(awb_number__icontains=query) | Shipment.objects.filter(customer__name__icontains=query) | Shipment.objects.filter(recipient_name__icontains=query)
    else:
        shipments_list = Shipment.objects.all().select_related('customer')
    
    paginator = Paginator(shipments_list, 10)
    page_number = request.GET.get('page')
    shipments = paginator.get_page(page_number)
    
    return render(request, 'shipments/list.html', {'shipments': shipments, 'query': query})

@group_required('SALES_OPS')
def shipment_add(request):
    if request.method == 'POST':
        form = ShipmentForm(request.POST)
        if form.is_valid():
            shipment = form.save(commit=False)
            shipment.input_by = request.user
            shipment.calculate_cost()
            shipment.save()
            # Auto-activate customer when they get their first shipment
            if not shipment.customer.is_active:
                shipment.customer.is_active = True
                shipment.customer.save(update_fields=['is_active'])
            # Auto-create invoice immediately so finance can confirm payment right away
            invoice = Invoice(
                shipment=shipment,
                customer=shipment.customer,
                subtotal=shipment.shipping_cost,
                ppn_rate=11.00,
                ppn_amount=shipment.ppn_amount,
                total_amount=shipment.total_cost,
                due_date=timezone.now().date() + timedelta(days=14),
                issued_by=request.user,
            )
            invoice.save()
            messages.success(request, f"Shipment {shipment.awb_number} created & invoice {invoice.invoice_number} generated.")
            return redirect('shipment_detail', pk=shipment.pk)
    else:
        form = ShipmentForm()
        
    customers_data = []
    for c in Customer.objects.filter(is_active=True):
        customers_data.append({
            'id': c.id,
            'name': c.name,
            'phone': c.phone,
            'address': c.address,
            'city': c.city
        })
        
    return render(request, 'shipments/add.html', {'form': form, 'customers_data': customers_data})

@login_required
def shipment_detail(request, pk):
    shipment = get_object_or_404(Shipment.objects.select_related('customer', 'invoice'), pk=pk)
    return render(request, 'shipments/detail.html', {'shipment': shipment})

VALID_TRANSITIONS = {
    'PENDING':   {'PICKUP'},
    'PICKUP':    {'TRANSIT'},
    'TRANSIT':   {'DELIVERED', 'RETURNED'},
    'DELIVERED': set(),
    'RETURNED':  set(),
}

@group_required('SALES_OPS')
def shipment_edit(request, pk):
    shipment = get_object_or_404(Shipment, pk=pk)
    if shipment.status != 'PENDING':
        messages.error(request, f"Cannot edit {shipment.awb_number} — only PENDING shipments can be edited.")
        return redirect('shipment_detail', pk=pk)
    if request.method == 'POST':
        form = ShipmentForm(request.POST, instance=shipment)
        if form.is_valid():
            s = form.save(commit=False)
            s.calculate_cost()
            s.save()
            messages.success(request, f"Shipment {shipment.awb_number} updated.")
            return redirect('shipment_detail', pk=pk)
    else:
        form = ShipmentForm(instance=shipment)
    return render(request, 'shipments/edit.html', {'form': form, 'shipment': shipment})


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
        with transaction.atomic():
            shipment.status = new_status
            shipment.save()
            if new_status == 'RETURNED':
                _handle_return_reversal(shipment, request.user)
        messages.success(request, f"Status for {shipment.awb_number} updated to {shipment.get_status_display()}")
    return redirect('shipment_detail', pk=pk)


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
        Invoice.objects.filter(pk=invoice.pk).update(
            notes=invoice.notes + note_line,
            payment_status='CANCELLED',
        )
    except Exception as e:
        logger.error(
            f"Return reversal GL posting failed for {invoice.invoice_number}: {e}",
            exc_info=True,
        )


SERVICE_REVENUE_MAP = {'REG': '4100', 'EXP': '4200', 'SDS': '4300', 'CAR': '4400'}

@group_required('FINANCE')
def generate_invoice(request, pk):
    shipment = get_object_or_404(Shipment, pk=pk)

    if hasattr(shipment, 'invoice'):
        messages.warning(request, f"Invoice already exists for {shipment.awb_number}")
        return redirect('invoice_detail', pk=shipment.invoice.pk)

    invoice = Invoice(
        shipment=shipment,
        customer=shipment.customer,
        subtotal=shipment.shipping_cost,
        ppn_rate=11.00,
        ppn_amount=shipment.ppn_amount,
        total_amount=shipment.total_cost,
        due_date=timezone.now().date() + timedelta(days=14),
        issued_by=request.user,
    )
    invoice.save()
    if getattr(invoice, '_gl_posted', False):
        messages.success(request, f"Invoice {invoice.invoice_number} generated for AWB {shipment.awb_number}")
    else:
        messages.warning(request, f"Invoice {invoice.invoice_number} saved, but GL journal entry failed — run 'python manage.py seed_coa' if accounts are missing.")
    return redirect('invoice_detail', pk=invoice.pk)