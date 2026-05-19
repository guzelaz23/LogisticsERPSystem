import logging
from django.db import models
from django.contrib.auth.models import User
from shipments.models import Shipment
from customers.models import Customer
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

PAYMENT_STATUS = [
    ('UNPAID','Unpaid'), ('PARTIAL','Partial'),
    ('PAID','Paid'), ('OVERDUE','Overdue'), ('CANCELLED','Cancelled'),
]
PAYMENT_METHOD = [
    ('TRANSFER','Bank Transfer'), ('CASH','Cash'), ('QRIS','QRIS'),
]

class Invoice(models.Model):
    invoice_number = models.CharField(max_length=30, unique=True)
    shipment       = models.OneToOneField(Shipment, on_delete=models.PROTECT)
    customer       = models.ForeignKey(Customer, on_delete=models.PROTECT)
    subtotal       = models.DecimalField(max_digits=12, decimal_places=2)
    ppn_rate       = models.DecimalField(max_digits=5, decimal_places=2, default=11.00)
    ppn_amount     = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount   = models.DecimalField(max_digits=12, decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='UNPAID')
    due_date       = models.DateField()
    issued_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    notes          = models.TextField(blank=True)

    def __str__(self):
        return self.invoice_number

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            ym = timezone.now().strftime('%Y%m')
            last = Invoice.objects.filter(invoice_number__startswith=f'INV-{ym}').order_by('-invoice_number').first()
            seq = 1
            if last:
                try:
                    seq = int(last.invoice_number.split('-')[-1]) + 1
                except ValueError:
                    seq = 1
            self.invoice_number = f"INV-{ym}-{seq:06d}"
        if not self.due_date:
            self.due_date = timezone.now().date() + timedelta(days=14)
        _is_new = not self.pk
        super().save(*args, **kwargs)
        if _is_new:
            self._gl_posted = self._create_journal_entry()

    def _create_journal_entry(self):
        from django.db import transaction as db_transaction
        from general_ledger.models import ChartOfAccount, JournalEntry, JournalEntryLine
        _SERVICE_REVENUE = {'REG': '4100', 'EXP': '4200', 'SDS': '4300', 'CAR': '4400'}
        try:
            with db_transaction.atomic():
                revenue_code = '4000'
                try:
                    if self.shipment_id and self.shipment.service_type:
                        revenue_code = _SERVICE_REVENUE.get(self.shipment.service_type, '4000')
                except Exception:
                    pass
                ar_account      = ChartOfAccount.objects.get(account_code='1200')
                revenue_account = ChartOfAccount.objects.get(account_code=revenue_code)
                ppn_account     = ChartOfAccount.objects.get(account_code='2100')
                entry_date = self.created_at.date() if self.created_at else timezone.now().date()
                entry = JournalEntry.objects.create(
                    entry_date  = entry_date,
                    description = f'Invoice issued: {self.invoice_number}',
                    reference   = self.invoice_number,
                    created_by  = self.issued_by,
                )
                JournalEntryLine.objects.create(
                    journal_entry=entry, account=ar_account,
                    description=f'AR - {self.invoice_number}',
                    debit_amount=self.total_amount, credit_amount=0,
                )
                JournalEntryLine.objects.create(
                    journal_entry=entry, account=revenue_account,
                    description=f'Revenue - {self.invoice_number}',
                    debit_amount=0, credit_amount=self.subtotal,
                )
                JournalEntryLine.objects.create(
                    journal_entry=entry, account=ppn_account,
                    description=f'PPN Payable - {self.invoice_number}',
                    debit_amount=0, credit_amount=self.ppn_amount,
                )
            return True
        except Exception as e:
            logger.error(
                f"GL posting failed for invoice {self.invoice_number}: {e}",
                exc_info=True,
            )
            return False

    class Meta:
        ordering = ['-created_at']

class Payment(models.Model):
    payment_number = models.CharField(max_length=30, unique=True)
    invoice        = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payments')
    amount_paid    = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD)
    payment_date   = models.DateField()
    bank_reference = models.CharField(max_length=100, blank=True)
    confirmed_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.payment_number

    def save(self, *args, **kwargs):
        if not self.payment_number:
            ym = timezone.now().strftime('%Y%m')
            last = Payment.objects.filter(payment_number__startswith=f'PAY-{ym}').order_by('-payment_number').first()
            seq = 1
            if last:
                try:
                    seq = int(last.payment_number.split('-')[-1]) + 1
                except ValueError:
                    seq = 1
            self.payment_number = f"PAY-{ym}-{seq:06d}"
        _is_new = not self.pk
        super().save(*args, **kwargs)
        # Auto-update invoice payment status
        invoice = self.invoice
        total_paid = sum(p.amount_paid for p in invoice.payments.all())
        if total_paid >= invoice.total_amount:
            invoice.payment_status = 'PAID'
        elif total_paid > 0:
            invoice.payment_status = 'PARTIAL'
        invoice.save(update_fields=['payment_status'])
        if _is_new:
            self._gl_posted = self._create_journal_entry()

    def _create_journal_entry(self):
        from django.db import transaction as db_transaction
        from general_ledger.models import ChartOfAccount, JournalEntry, JournalEntryLine
        try:
            with db_transaction.atomic():
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
            return True
        except Exception as e:
            logger.error(
                f"GL posting failed for payment {self.payment_number} "
                f"(invoice {self.invoice.invoice_number}): {e}",
                exc_info=True
            )
            return False

    class Meta:
        ordering = ['-created_at']
