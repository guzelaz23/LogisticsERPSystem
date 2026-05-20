from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from ais_finalproject.utils import group_required
from .models import ChartOfAccount, ACCOUNT_TYPE_CHOICES, NORMAL_BALANCE


@group_required('MANAGEMENT')
def coa_list(request):
    accounts = ChartOfAccount.objects.all()
    return render(request, 'general_ledger/coa_list.html', {
        'accounts': accounts,
    })


@group_required('MANAGEMENT')
def coa_create(request):
    if request.method == 'POST':
        code    = request.POST.get('account_code', '').strip()
        name    = request.POST.get('account_name', '').strip()
        a_type  = request.POST.get('account_type', '')
        balance = request.POST.get('normal_balance', '')

        if not code or not name or not a_type or not balance:
            messages.error(request, 'All fields are required.')
        elif ChartOfAccount.objects.filter(account_code=code).exists():
            messages.error(request, f'Account code {code} already exists.')
        else:
            ChartOfAccount.objects.create(
                account_code=code,
                account_name=name,
                account_type=a_type,
                normal_balance=balance,
                is_active=True,
            )
            messages.success(request, f'Account {code} - {name} created successfully.')
            return redirect('coa_list')

    return render(request, 'general_ledger/coa_form.html', {
        'account_types': ACCOUNT_TYPE_CHOICES,
        'normal_balances': NORMAL_BALANCE,
        'action': 'Create',
    })


@group_required('MANAGEMENT')
def coa_edit(request, pk):
    account = get_object_or_404(ChartOfAccount, pk=pk)

    if request.method == 'POST':
        name    = request.POST.get('account_name', '').strip()
        a_type  = request.POST.get('account_type', '')
        balance = request.POST.get('normal_balance', '')
        active  = request.POST.get('is_active') == 'on'

        if not name or not a_type or not balance:
            messages.error(request, 'All fields are required.')
        else:
            account.account_name   = name
            account.account_type   = a_type
            account.normal_balance = balance
            account.is_active      = active
            account.save()
            messages.success(request, f'Account {account.account_code} updated.')
            return redirect('coa_list')

    return render(request, 'general_ledger/coa_form.html', {
        'account':        account,
        'account_types':  ACCOUNT_TYPE_CHOICES,
        'normal_balances': NORMAL_BALANCE,
        'action':         'Edit',
    })
