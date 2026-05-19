from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.urls import reverse
from decimal import Decimal
from customers.models import Customer
from shipments.models import Shipment


def make_ops_user():
    group, _ = Group.objects.get_or_create(name='SALES_OPS')
    user = User.objects.create_user('ops_test', password='pass')
    user.groups.add(group)
    return user


def make_customer_for_test():
    return Customer.objects.create(
        name='PT Guard Test', phone='081', address='Jl. A', city='Jakarta'
    )


def make_shipment_with_status(customer, status, awb):
    return Shipment.objects.create(
        awb_number=awb,
        customer=customer,
        sender_name='S', sender_phone='1', sender_address='A',
        origin_city='Jakarta',
        recipient_name='R', recipient_phone='2', recipient_address='B',
        destination_city='Surabaya',
        service_type='REG',
        weight_kg=Decimal('1.0'),
        shipping_cost=Decimal('8000'),
        ppn_amount=Decimal('880'),
        total_cost=Decimal('8880'),
        status=status,
    )


class StatusTransitionGuardTest(TestCase):
    def setUp(self):
        self.user = make_ops_user()
        self.customer = make_customer_for_test()
        self.client.login(username='ops_test', password='pass')

    def _update(self, shipment, new_status):
        return self.client.post(
            reverse('shipment_update_status', kwargs={'pk': shipment.pk}),
            {'status': new_status},
        )

    def test_pending_to_pickup_allowed(self):
        s = make_shipment_with_status(self.customer, 'PENDING', 'AWB-G-001')
        self._update(s, 'PICKUP')
        s.refresh_from_db()
        self.assertEqual(s.status, 'PICKUP')

    def test_pickup_to_transit_allowed(self):
        s = make_shipment_with_status(self.customer, 'PICKUP', 'AWB-G-002')
        self._update(s, 'TRANSIT')
        s.refresh_from_db()
        self.assertEqual(s.status, 'TRANSIT')

    def test_transit_to_delivered_allowed(self):
        s = make_shipment_with_status(self.customer, 'TRANSIT', 'AWB-G-003')
        self._update(s, 'DELIVERED')
        s.refresh_from_db()
        self.assertEqual(s.status, 'DELIVERED')

    def test_transit_to_returned_allowed(self):
        s = make_shipment_with_status(self.customer, 'TRANSIT', 'AWB-G-004')
        self._update(s, 'RETURNED')
        s.refresh_from_db()
        self.assertEqual(s.status, 'RETURNED')

    def test_delivered_to_pending_rejected(self):
        s = make_shipment_with_status(self.customer, 'DELIVERED', 'AWB-G-005')
        self._update(s, 'PENDING')
        s.refresh_from_db()
        self.assertEqual(s.status, 'DELIVERED')

    def test_pending_to_delivered_rejected(self):
        s = make_shipment_with_status(self.customer, 'PENDING', 'AWB-G-006')
        self._update(s, 'DELIVERED')
        s.refresh_from_db()
        self.assertEqual(s.status, 'PENDING')

    def test_returned_is_terminal(self):
        s = make_shipment_with_status(self.customer, 'RETURNED', 'AWB-G-007')
        self._update(s, 'DELIVERED')
        s.refresh_from_db()
        self.assertEqual(s.status, 'RETURNED')

    def test_delivered_is_terminal(self):
        s = make_shipment_with_status(self.customer, 'DELIVERED', 'AWB-G-008')
        self._update(s, 'TRANSIT')
        s.refresh_from_db()
        self.assertEqual(s.status, 'DELIVERED')


import datetime
from billing.models import Invoice
from general_ledger.models import ChartOfAccount, JournalEntry, JournalEntryLine


def make_coa():
    ChartOfAccount.objects.create(
        account_code='1200', account_name='AR',
        account_type='ASSET', normal_balance='DEBIT',
    )
    ChartOfAccount.objects.create(
        account_code='2100', account_name='PPN Payable',
        account_type='LIABILITY', normal_balance='CREDIT',
    )
    ChartOfAccount.objects.create(
        account_code='4100', account_name='Revenue - Regular',
        account_type='REVENUE', normal_balance='CREDIT',
    )
    ChartOfAccount.objects.create(
        account_code='4900', account_name='Sales Returns & Allowances',
        account_type='REVENUE', normal_balance='DEBIT',
    )


class ReturnReversalTest(TestCase):
    def setUp(self):
        self.user = make_ops_user()
        self.customer = make_customer_for_test()
        make_coa()
        self.client.login(username='ops_test', password='pass')
        self.shipment = make_shipment_with_status(self.customer, 'TRANSIT', 'AWB-R-001')
        self.invoice = Invoice.objects.create(
            shipment=self.shipment,
            customer=self.customer,
            subtotal=Decimal('8000'),
            ppn_rate=Decimal('11.00'),
            ppn_amount=Decimal('880'),
            total_amount=Decimal('8880'),
            due_date=datetime.date.today(),
            issued_by=self.user,
        )

    def _return_shipment(self):
        return self.client.post(
            reverse('shipment_update_status', kwargs={'pk': self.shipment.pk}),
            {'status': 'RETURNED'},
        )

    def test_return_creates_reversal_journal_entry(self):
        je_count_before = JournalEntry.objects.count()
        self._return_shipment()
        self.assertEqual(JournalEntry.objects.count(), je_count_before + 1)

    def test_reversal_je_has_correct_lines(self):
        self._return_shipment()
        reversal_je = JournalEntry.objects.filter(reference__startswith='RET-').last()
        self.assertIsNotNone(reversal_je)
        lines = list(reversal_je.lines.all())
        self.assertEqual(len(lines), 3)
        contra = next(l for l in lines if l.account.account_code == '4900')
        self.assertEqual(contra.debit_amount, Decimal('8000'))
        self.assertEqual(contra.credit_amount, Decimal('0'))
        ppn = next(l for l in lines if l.account.account_code == '2100')
        self.assertEqual(ppn.debit_amount, Decimal('880'))
        self.assertEqual(ppn.credit_amount, Decimal('0'))
        ar = next(l for l in lines if l.account.account_code == '1200')
        self.assertEqual(ar.debit_amount, Decimal('0'))
        self.assertEqual(ar.credit_amount, Decimal('8880'))

    def test_return_updates_invoice_notes(self):
        self._return_shipment()
        self.invoice.refresh_from_db()
        self.assertIn('RETURNED', self.invoice.notes)

    def test_return_without_invoice_creates_no_extra_je(self):
        shipment_no_inv = make_shipment_with_status(self.customer, 'TRANSIT', 'AWB-R-002')
        je_count_before = JournalEntry.objects.count()
        response = self.client.post(
            reverse('shipment_update_status', kwargs={'pk': shipment_no_inv.pk}),
            {'status': 'RETURNED'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(JournalEntry.objects.count(), je_count_before)
