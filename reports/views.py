import csv
import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import date as _date
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth, ExtractYear, ExtractMonth
from shipments.models import Shipment, SERVICE_CHOICES, STATUS_CHOICES
from billing.models import Invoice


@login_required
def shipment_report(request):
    start_date    = request.GET.get('start_date')
    end_date      = request.GET.get('end_date')
    service_type  = request.GET.get('service_type', '')
    status_filter = request.GET.get('status', '')
    export        = request.GET.get('export', '')

    shipments = Shipment.objects.select_related('customer').all()
    if start_date:
        shipments = shipments.filter(created_at__date__gte=start_date)
    if end_date:
        shipments = shipments.filter(created_at__date__lte=end_date)
    if service_type:
        shipments = shipments.filter(service_type=service_type)
    if status_filter:
        shipments = shipments.filter(status=status_filter)

    if export == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="shipment_report.csv"'
        writer = csv.writer(response)
        writer.writerow(['AWB Number', 'Date', 'Customer', 'Origin', 'Destination',
                         'Service', 'Weight (kg)', 'Shipping Cost', 'PPN', 'Total', 'Status'])
        for s in shipments:
            writer.writerow([
                s.awb_number,
                s.created_at.strftime('%Y-%m-%d'),
                s.customer.name,
                s.origin_city,
                s.destination_city,
                s.get_service_type_display(),
                s.weight_kg,
                s.shipping_cost,
                s.ppn_amount,
                s.total_cost,
                s.get_status_display(),
            ])
        return response

    status_counts   = shipments.values('status').annotate(total=Count('id'))
    total_shipments = shipments.count()
    total_revenue   = shipments.aggregate(total=Sum('total_cost'))['total'] or 0
    total_weight    = shipments.aggregate(t=Sum('weight_kg'))['t'] or 0

    return render(request, 'reports/shipment_report.html', {
        'shipments':       shipments[:50],
        'status_counts':   status_counts,
        'start_date':      start_date,
        'end_date':        end_date,
        'service_type':    service_type,
        'status_filter':   status_filter,
        'service_choices': SERVICE_CHOICES,
        'status_choices':  STATUS_CHOICES,
        'total_shipments': total_shipments,
        'total_revenue':   total_revenue,
        'total_weight':    total_weight,
    })


@login_required
def revenue_report(request):
    start_date = request.GET.get('start_date')
    end_date   = request.GET.get('end_date')
    export     = request.GET.get('export', '')

    invoices = Invoice.objects.select_related('shipment').exclude(
        payment_status='CANCELLED'
    ).exclude(
        shipment__status='RETURNED'
    )
    if start_date:
        invoices = invoices.filter(created_at__date__gte=start_date)
    if end_date:
        invoices = invoices.filter(created_at__date__lte=end_date)

    total_shipments = invoices.count()
    total_revenue   = invoices.aggregate(total=Sum('subtotal'))['total'] or 0
    total_ppn       = invoices.aggregate(total=Sum('ppn_amount'))['total'] or 0
    # subtotal IS the net service revenue (excl. VAT); PPN is a liability, not a revenue deduction
    net_revenue     = total_revenue

    monthly_raw = invoices.annotate(
        yr=ExtractYear('created_at'),
        mo=ExtractMonth('created_at'),
    ).values('yr', 'mo').annotate(
        shipments_count=Count('id'),
        revenue=Sum('subtotal'),
        ppn=Sum('ppn_amount'),
        net=Sum('subtotal'),
    ).order_by('yr', 'mo')

    monthly_data = [
        {
            'month': _date(item['yr'], item['mo'], 1),
            'shipments_count': item['shipments_count'],
            'revenue': item['revenue'] or 0,
            'ppn': item['ppn'] or 0,
            'net': item['net'] or 0,
        }
        for item in monthly_raw
    ]

    if export == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="revenue_report.csv"'
        writer = csv.writer(response)
        writer.writerow(['Month', 'Invoices', 'Service Revenue (excl. PPN)', 'PPN Collected (11%)', 'Service Revenue (excl. PPN)'])
        for item in monthly_data:
            writer.writerow([
                item['month'].strftime('%B %Y'),
                item['shipments_count'],
                item['revenue'],
                item['ppn'],
                item['net'],
            ])
        writer.writerow(['TOTAL', total_shipments, total_revenue, total_ppn, net_revenue])
        return response

    # Chart: oldest → newest (ascending, already ordered)
    chart_months  = [item['month'].strftime('%b %Y') for item in monthly_data]
    chart_revenue = [float(item['revenue']) for item in monthly_data]

    # Template table: newest → oldest
    monthly_data  = list(reversed(monthly_data))

    service_data = invoices.values('shipment__service_type').annotate(total=Sum('subtotal'))
    pie_labels   = [item['shipment__service_type'] for item in service_data]
    pie_data     = [float(item['total']) for item in service_data]

    context = {
        'start_date':      start_date,
        'end_date':        end_date,
        'total_shipments': total_shipments,
        'total_revenue':   total_revenue,
        'total_ppn':       total_ppn,
        'net_revenue':     net_revenue,
        'monthly_data':    monthly_data,
        'chart_months':    json.dumps(chart_months),
        'chart_revenue':   json.dumps(chart_revenue),
        'pie_labels':      json.dumps(pie_labels),
        'pie_data':        json.dumps(pie_data),
    }
    return render(request, 'reports/revenue_report.html', context)


@login_required
def trial_balance(request):
    from general_ledger.models import ChartOfAccount
    from django.db.models import Sum, Q
    from django.db.models.functions import Coalesce
    from django.utils import timezone

    as_of_date = request.GET.get('as_of_date') or timezone.now().date().isoformat()
    date_q = Q(journalentryline__journal_entry__entry_date__lte=as_of_date)

    accounts = list(
        ChartOfAccount.objects.filter(is_active=True).annotate(
            debit_total=Coalesce(Sum('journalentryline__debit_amount', filter=date_q), Decimal('0')),
            credit_total=Coalesce(Sum('journalentryline__credit_amount', filter=date_q), Decimal('0')),
        ).order_by('account_code')
    )
    for acc in accounts:
        acc.balance = (
            acc.debit_total - acc.credit_total
            if acc.normal_balance == 'DEBIT'
            else acc.credit_total - acc.debit_total
        )

    total_debit  = sum(a.debit_total  for a in accounts)
    total_credit = sum(a.credit_total for a in accounts)
    is_balanced  = abs(total_debit - total_credit) < Decimal('0.01')

    return render(request, 'reports/trial_balance.html', {
        'gl_entries':   accounts,
        'total_debit':  total_debit,
        'total_credit': total_credit,
        'is_balanced':  is_balanced,
        'as_of_date':   as_of_date,
    })


@login_required
def income_statement(request):
    from general_ledger.models import ChartOfAccount
    from django.db.models import Sum, Q
    from django.db.models.functions import Coalesce

    start_date = request.GET.get('start_date')
    end_date   = request.GET.get('end_date')
    export     = request.GET.get('export', '')

    if start_date and end_date:
        period_label = f"{start_date} to {end_date}"
    elif start_date:
        period_label = f"From {start_date}"
    elif end_date:
        period_label = f"Up to {end_date}"
    else:
        period_label = "All Periods"

    date_q = Q()
    if start_date:
        date_q &= Q(journalentryline__journal_entry__entry_date__gte=start_date)
    if end_date:
        date_q &= Q(journalentryline__journal_entry__entry_date__lte=end_date)

    def get_accounts(account_type):
        return list(
            ChartOfAccount.objects.filter(account_type=account_type, is_active=True).annotate(
                debit_total=Coalesce(Sum('journalentryline__debit_amount', filter=date_q), Decimal('0')),
                credit_total=Coalesce(Sum('journalentryline__credit_amount', filter=date_q), Decimal('0')),
            ).order_by('account_code')
        )

    revenue_list = get_accounts('REVENUE')
    for acc in revenue_list:
        acc.balance = acc.credit_total - acc.debit_total

    expense_list = get_accounts('EXPENSE')
    for acc in expense_list:
        acc.balance = acc.debit_total - acc.credit_total

    gross_revenue_list  = [a for a in revenue_list if a.account_code != '4900']
    contra_revenue_list = [a for a in revenue_list if a.account_code == '4900']

    # Contra-revenue (4900) has DEBIT normal balance — recompute correctly
    for acc in contra_revenue_list:
        acc.balance = acc.debit_total - acc.credit_total

    total_gross_revenue = sum(a.balance for a in gross_revenue_list)
    total_contra        = sum(a.balance for a in contra_revenue_list)
    total_revenue       = total_gross_revenue - total_contra
    total_expense       = sum(a.balance for a in expense_list)
    net_income          = total_revenue - total_expense

    if export == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="income_statement.csv"'
        writer = csv.writer(response)
        writer.writerow(['SAP Express Logistik — Income Statement'])
        writer.writerow([f'Period: {period_label}'])
        writer.writerow([])
        writer.writerow(['Account No.', 'Account Name', 'Amount (Rp)'])
        writer.writerow(['GROSS REVENUE', '', ''])
        for acc in gross_revenue_list:
            writer.writerow([acc.account_code, acc.account_name, acc.balance])
        if contra_revenue_list:
            writer.writerow(['REVENUE DEDUCTIONS', '', ''])
            for acc in contra_revenue_list:
                writer.writerow([acc.account_code, acc.account_name, acc.balance])
        writer.writerow(['', 'NET REVENUE', total_revenue])
        writer.writerow([])
        writer.writerow(['OPERATING EXPENSES', '', ''])
        for acc in expense_list:
            writer.writerow([acc.account_code, acc.account_name, acc.balance])
        writer.writerow(['', 'TOTAL EXPENSES', total_expense])
        writer.writerow([])
        writer.writerow(['', 'NET INCOME', net_income])
        return response

    return render(request, 'reports/income_statement.html', {
        'start_date':          start_date,
        'end_date':            end_date,
        'period_label':        period_label,
        'gross_revenue_gl':    gross_revenue_list,
        'contra_revenue_gl':   contra_revenue_list,
        'expense_gl':          expense_list,
        'total_gross_revenue': total_gross_revenue,
        'total_contra':        total_contra,
        'total_revenue':       total_revenue,
        'total_expense':       total_expense,
        'net_income':          net_income,
    })


@login_required
def balance_sheet(request):
    from general_ledger.models import ChartOfAccount
    from django.db.models import Sum, Q
    from django.db.models.functions import Coalesce
    from django.utils import timezone

    as_of_date = request.GET.get('as_of_date') or timezone.now().date().isoformat()
    export     = request.GET.get('export', '')
    date_q = Q(journalentryline__journal_entry__entry_date__lte=as_of_date)

    def get_accounts(account_type):
        return list(
            ChartOfAccount.objects.filter(account_type=account_type, is_active=True).annotate(
                debit_total=Coalesce(Sum('journalentryline__debit_amount', filter=date_q), Decimal('0')),
                credit_total=Coalesce(Sum('journalentryline__credit_amount', filter=date_q), Decimal('0')),
            ).order_by('account_code')
        )

    asset_list     = get_accounts('ASSET')
    liability_list = get_accounts('LIABILITY')
    equity_list    = get_accounts('EQUITY')
    revenue_list   = get_accounts('REVENUE')
    expense_list   = get_accounts('EXPENSE')

    for acc in asset_list:
        acc.balance = acc.debit_total - acc.credit_total
    for acc in liability_list:
        acc.balance = acc.credit_total - acc.debit_total
    for acc in equity_list:
        acc.balance = acc.credit_total - acc.debit_total
    for acc in revenue_list:
        acc.balance = acc.credit_total - acc.debit_total
    for acc in expense_list:
        acc.balance = acc.debit_total - acc.credit_total

    # current assets: code < 1400; non-current: >= 1400
    current_asset_list    = [a for a in asset_list if int(a.account_code) < 1400]
    noncurrent_asset_list = [a for a in asset_list if int(a.account_code) >= 1400]
    total_current_assets    = sum(a.balance for a in current_asset_list)
    total_noncurrent_assets = sum(a.balance for a in noncurrent_asset_list)

    net_income        = sum(a.balance for a in revenue_list) - sum(a.balance for a in expense_list)
    total_assets      = sum(a.balance for a in asset_list)
    total_liabilities = sum(a.balance for a in liability_list)
    total_equity      = sum(a.balance for a in equity_list) + net_income
    is_balanced       = abs(total_assets - (total_liabilities + total_equity)) < Decimal('1')

    if export == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="balance_sheet.csv"'
        writer = csv.writer(response)
        writer.writerow(['SAP Express Logistik — Balance Sheet'])
        writer.writerow([f'As of: {as_of_date}'])
        writer.writerow([])
        writer.writerow(['Account No.', 'Account Name', 'Balance (Rp)'])
        writer.writerow(['CURRENT ASSETS', '', ''])
        for acc in current_asset_list:
            writer.writerow([acc.account_code, acc.account_name, acc.balance])
        writer.writerow(['', 'Total Current Assets', total_current_assets])
        if noncurrent_asset_list:
            writer.writerow(['NON-CURRENT ASSETS', '', ''])
            for acc in noncurrent_asset_list:
                writer.writerow([acc.account_code, acc.account_name, acc.balance])
            writer.writerow(['', 'Total Non-Current Assets', total_noncurrent_assets])
        writer.writerow(['', 'TOTAL ASSETS', total_assets])
        writer.writerow([])
        writer.writerow(['LIABILITIES', '', ''])
        for acc in liability_list:
            writer.writerow([acc.account_code, acc.account_name, acc.balance])
        writer.writerow(['', 'Total Liabilities', total_liabilities])
        writer.writerow([])
        writer.writerow(['EQUITY', '', ''])
        for acc in equity_list:
            writer.writerow([acc.account_code, acc.account_name, acc.balance])
        writer.writerow(['', 'Net Income (Unappropriated)', net_income])
        writer.writerow(['', 'Total Equity', total_equity])
        writer.writerow([])
        writer.writerow(['', 'TOTAL LIABILITIES + EQUITY', total_liabilities + total_equity])
        return response

    return render(request, 'reports/balance_sheet.html', {
        'current_asset_gl':            current_asset_list,
        'noncurrent_asset_gl':         noncurrent_asset_list,
        'liability_gl':                liability_list,
        'equity_gl':                   equity_list,
        'total_current_assets':        total_current_assets,
        'total_noncurrent_assets':     total_noncurrent_assets,
        'total_assets':                total_assets,
        'total_liabilities':           total_liabilities,
        'total_equity':                total_equity,
        'total_liabilities_equity':    total_liabilities + total_equity,
        'net_income':                  net_income,
        'is_balanced':                 is_balanced,
        'as_of_date':                  as_of_date,
        'report_date':                 as_of_date,
    })


@login_required
def ar_aging(request):
    from django.utils import timezone
    from django.db.models import Prefetch
    from billing.models import Payment

    today = timezone.now().date()

    Invoice.objects.filter(
        payment_status='UNPAID',
        due_date__lt=today,
    ).update(payment_status='OVERDUE')

    outstanding = (
        Invoice.objects
        .filter(payment_status__in=['UNPAID', 'PARTIAL', 'OVERDUE'])
        .select_related('customer', 'shipment')
        .prefetch_related('payments')
        .order_by('due_date')
    )

    buckets = {'current': [], 'b1_30': [], 'b31_60': [], 'b61_90': [], 'b90plus': []}
    for inv in outstanding:
        paid = sum(p.amount_paid for p in inv.payments.all())
        inv.outstanding_amount = inv.total_amount - paid
        inv.days_overdue = (today - inv.due_date).days
        if inv.days_overdue <= 0:
            buckets['current'].append(inv)
        elif inv.days_overdue <= 30:
            buckets['b1_30'].append(inv)
        elif inv.days_overdue <= 60:
            buckets['b31_60'].append(inv)
        elif inv.days_overdue <= 90:
            buckets['b61_90'].append(inv)
        else:
            buckets['b90plus'].append(inv)

    def total(lst):
        return sum(inv.outstanding_amount for inv in lst)

    aging_display = [
        ('Current (Not Yet Due)',  '#10b981', buckets['current']),
        ('1–30 Days Overdue',      '#f59e0b', buckets['b1_30']),
        ('31–60 Days Overdue',     '#f97316', buckets['b31_60']),
        ('61–90 Days Overdue',     '#ef4444', buckets['b61_90']),
        ('>90 Days Overdue',       '#991b1b', buckets['b90plus']),
    ]

    return render(request, 'reports/ar_aging.html', {
        'today':         today,
        'buckets':       buckets,
        'aging_display': aging_display,
        'totals': {
            'current': total(buckets['current']),
            'b1_30':   total(buckets['b1_30']),
            'b31_60':  total(buckets['b31_60']),
            'b61_90':  total(buckets['b61_90']),
            'b90plus': total(buckets['b90plus']),
            'grand':   sum(total(v) for v in buckets.values()),
        },
    })


@login_required
def cash_flow_statement(request):
    from general_ledger.models import JournalEntryLine
    from django.db.models import Sum, Q
    from django.utils import timezone

    start_date = request.GET.get('start_date')
    end_date   = request.GET.get('end_date')
    export     = request.GET.get('export', '')

    if start_date and end_date:
        period_label = f"{start_date} to {end_date}"
    elif start_date:
        period_label = f"From {start_date}"
    elif end_date:
        period_label = f"Up to {end_date}"
    else:
        period_label = "All Periods"

    cash_qs  = JournalEntryLine.objects.filter(account__account_code='1100')

    period_q = Q()
    if start_date:
        period_q &= Q(journal_entry__entry_date__gte=start_date)
    if end_date:
        period_q &= Q(journal_entry__entry_date__lte=end_date)

    period_lines = cash_qs.filter(period_q)

    # Debit to Cash = money received (customers paying invoices)
    cash_in  = period_lines.aggregate(t=Sum('debit_amount'))['t']  or Decimal('0')
    # Credit to Cash = money paid out (expenses)
    cash_out = period_lines.aggregate(t=Sum('credit_amount'))['t'] or Decimal('0')
    net_cash = cash_in - cash_out

    # Beginning balance = all cash activity before the start date
    if start_date:
        before_lines     = cash_qs.filter(journal_entry__entry_date__lt=start_date)
        beg_in           = before_lines.aggregate(t=Sum('debit_amount'))['t']  or Decimal('0')
        beg_out          = before_lines.aggregate(t=Sum('credit_amount'))['t'] or Decimal('0')
        beginning_balance = beg_in - beg_out
    else:
        beginning_balance = Decimal('0')

    ending_balance = beginning_balance + net_cash

    # Detail rows for the transaction table
    detail = (
        period_lines
        .select_related('journal_entry')
        .order_by('journal_entry__entry_date', 'journal_entry__id')
    )

    if export == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="cash_flow.csv"'
        writer = csv.writer(response)
        writer.writerow(['SAP Express — Cash Flow Statement'])
        writer.writerow([f'Period: {period_label}'])
        writer.writerow([])
        writer.writerow(['OPERATING ACTIVITIES', ''])
        writer.writerow(['Cash Received from Customers', cash_in])
        writer.writerow(['Cash Paid for Expenses', -cash_out])
        writer.writerow(['Net Cash from Operating Activities', net_cash])
        writer.writerow([])
        writer.writerow(['Beginning Cash Balance', beginning_balance])
        writer.writerow(['Ending Cash Balance', ending_balance])
        writer.writerow([])
        writer.writerow(['Date', 'Journal No.', 'Description', 'Cash In', 'Cash Out'])
        for line in detail:
            writer.writerow([
                line.journal_entry.entry_date,
                line.journal_entry.entry_number,
                line.journal_entry.description,
                line.debit_amount  or '',
                line.credit_amount or '',
            ])
        return response

    return render(request, 'reports/cash_flow.html', {
        'start_date':        start_date,
        'end_date':          end_date,
        'period_label':      period_label,
        'cash_in':           cash_in,
        'cash_out':          cash_out,
        'net_cash':          net_cash,
        'beginning_balance': beginning_balance,
        'ending_balance':    ending_balance,
        'detail':            detail,
    })


@login_required
def journal_entries(request):
    from general_ledger.models import JournalEntry
    from django.core.paginator import Paginator

    start_date = request.GET.get('start_date')
    end_date   = request.GET.get('end_date')

    entries = JournalEntry.objects.prefetch_related('lines__account').order_by('-entry_date')
    if start_date:
        entries = entries.filter(entry_date__gte=start_date)
    if end_date:
        entries = entries.filter(entry_date__lte=end_date)

    paginator = Paginator(entries, 20)
    page      = request.GET.get('page')
    entries   = paginator.get_page(page)

    return render(request, 'reports/journal_entries.html', {
        'entries':    entries,
        'start_date': start_date,
        'end_date':   end_date,
    })


@login_required
def delete_journal_entry(request, pk):
    from general_ledger.models import JournalEntry

    if not request.user.is_superuser:
        messages.error(request, "Only administrators can delete journal entries.")
        return redirect('journal_entries')

    if request.method != 'POST':
        return redirect('journal_entries')

    entry = get_object_or_404(JournalEntry, pk=pk)
    entry_number = entry.entry_number
    entry.delete()
    messages.success(request, f"Journal entry {entry_number} has been deleted.")
    return redirect('journal_entries')
