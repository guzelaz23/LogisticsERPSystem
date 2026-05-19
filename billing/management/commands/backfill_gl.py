from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = (
        'Backfill missing GL journal entries for historical invoices and payments. '
        'Prerequisite: run `python manage.py seed_coa` before this command.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be created without writing to the database.',
        )

    def handle(self, *args, **options):
        from billing.models import Invoice, Payment
        from general_ledger.models import JournalEntry

        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes will be written.\n'))

        inv_processed = inv_skipped = inv_failed = 0
        pay_processed = pay_skipped = pay_failed = 0

        # ── Invoices ──────────────────────────────────────────────────────────
        self.stdout.write('Processing invoices...')
        for invoice in Invoice.objects.all().iterator():
            has_je = JournalEntry.objects.filter(reference=invoice.invoice_number).exists()
            if has_je:
                inv_skipped += 1
                continue
            if dry_run:
                self.stdout.write(f'  [DRY] Would create JE for invoice {invoice.invoice_number}')
                inv_processed += 1
                continue
            try:
                with transaction.atomic():
                    invoice._create_journal_entry()
                inv_processed += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'  FAILED invoice {invoice.invoice_number}: {e}'))
                inv_failed += 1

        # ── Payments ──────────────────────────────────────────────────────────
        self.stdout.write('Processing payments...')
        for payment in Payment.objects.select_related('invoice').iterator():
            has_je = JournalEntry.objects.filter(
                reference=payment.invoice.invoice_number,
                entry_date=payment.payment_date,
            ).exists()
            if has_je:
                pay_skipped += 1
                continue
            if dry_run:
                self.stdout.write(f'  [DRY] Would create JE for payment {payment.payment_number}')
                pay_processed += 1
                continue
            try:
                with transaction.atomic():
                    payment._create_journal_entry()
                pay_processed += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'  FAILED payment {payment.payment_number}: {e}'))
                pay_failed += 1

        # ── Rebuild GeneralLedger ─────────────────────────────────────────────
        if not dry_run:
            self.stdout.write('\nRebuilding GeneralLedger totals...')
            from decimal import Decimal
            from django.db.models import Sum
            from django.db.models.functions import Coalesce
            from general_ledger.models import ChartOfAccount, GeneralLedger, JournalEntryLine as JELine

            account_totals = (
                JELine.objects
                .values('account')
                .annotate(
                    debit=Coalesce(Sum('debit_amount'), Decimal('0')),
                    credit=Coalesce(Sum('credit_amount'), Decimal('0')),
                )
            )
            gl_count = 0
            for row in account_totals:
                account = ChartOfAccount.objects.get(pk=row['account'])
                GeneralLedger.objects.update_or_create(
                    account=account,
                    defaults={'debit_total': row['debit'], 'credit_total': row['credit']},
                )
                gl_count += 1
            self.stdout.write(self.style.SUCCESS(f'GeneralLedger: rebuilt {gl_count} account(s).'))

        # ── Summary ───────────────────────────────────────────────────────────
        action = 'Would create' if dry_run else 'Created'
        self.stdout.write('\n── Summary ──────────────────────────────────')
        self.stdout.write(self.style.SUCCESS(
            f'Invoices : {action} {inv_processed}, skipped {inv_skipped}, failed {inv_failed}'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'Payments : {action} {pay_processed}, skipped {pay_skipped}, failed {pay_failed}'
        ))
