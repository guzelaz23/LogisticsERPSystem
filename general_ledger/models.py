from decimal import Decimal
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save
from django.dispatch import receiver
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


@receiver(post_save, sender=JournalEntryLine)
def _sync_general_ledger(sender, instance, **kwargs):
    agg = JournalEntryLine.objects.filter(account=instance.account).aggregate(
        debit=Coalesce(Sum('debit_amount'), Decimal('0')),
        credit=Coalesce(Sum('credit_amount'), Decimal('0')),
    )
    GeneralLedger.objects.update_or_create(
        account=instance.account,
        defaults={
            'debit_total': agg['debit'],
            'credit_total': agg['credit'],
        },
    )
