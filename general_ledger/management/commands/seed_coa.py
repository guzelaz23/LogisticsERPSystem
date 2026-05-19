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
    ('4400', 'Revenue - Cargo',            'REVENUE',   'CREDIT'),
    ('4900', 'Sales Returns & Allowances', 'REVENUE',   'DEBIT'),
    ('5100', 'Operating Expenses',         'EXPENSE',   'DEBIT'),
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
