from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from shipments.models import Shipment
from billing.models import Invoice
import json

@login_required
def dashboard(request):
    from django.utils import timezone
    from dateutil.relativedelta import relativedelta
    from billing.models import Payment

    today = timezone.now()
    first_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # KPI Cards
    total_shipments_month = Shipment.objects.filter(created_at__gte=first_of_month).count()
    total_shipments_all   = Shipment.objects.count()

    revenue_month = Shipment.objects.filter(
        status='DELIVERED', created_at__gte=first_of_month
    ).aggregate(total=Sum('total_cost'))['total'] or 0

    # Accounts Receivable (AR) — includes OVERDUE invoices
    outstanding_ar = Invoice.objects.filter(
        payment_status__in=['UNPAID', 'PARTIAL', 'OVERDUE']
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    pending_invoices = Invoice.objects.filter(payment_status__in=['UNPAID', 'PARTIAL', 'OVERDUE']).count()
    overdue_invoices = Invoice.objects.filter(payment_status='OVERDUE').count()
    paid_invoices    = Invoice.objects.filter(payment_status='PAID').count()

    total_collected = Payment.objects.filter(
        created_at__gte=first_of_month
    ).aggregate(total=Sum('amount_paid'))['total'] or 0

    recent_invoices = Invoice.objects.select_related(
        'customer', 'shipment'
    ).order_by('-created_at')[:6]

    recent_shipments = Shipment.objects.select_related('customer').order_by('-created_at')[:5]

    # Revenue Chart (Last 6 Months)
    chart_labels = []
    chart_data   = []
    for i in range(5, -1, -1):
        dt    = today - relativedelta(months=i)
        start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end   = start + relativedelta(months=1)
        rev   = Shipment.objects.filter(
            status='DELIVERED', created_at__gte=start, created_at__lt=end
        ).aggregate(total=Sum('total_cost'))['total'] or 0
        chart_labels.append(dt.strftime('%b'))
        chart_data.append(float(rev))

    context = {
        'today':                 today,
        'total_shipments_month': total_shipments_month,
        'total_shipments_all':   total_shipments_all,
        'revenue_month':         revenue_month,
        'outstanding_ar':        outstanding_ar,
        'pending_invoices':      pending_invoices,
        'overdue_invoices':      overdue_invoices,
        'paid_invoices':         paid_invoices,
        'total_collected':       total_collected,
        'recent_invoices':       recent_invoices,
        'recent_shipments':      recent_shipments,
        'chart_labels':          json.dumps(chart_labels),
        'chart_data':            json.dumps(chart_data),
    }
    return render(request, 'ais_finalproject/dashboard.html', context)
