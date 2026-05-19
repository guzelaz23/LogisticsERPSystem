from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from decimal import Decimal
import datetime
from customers.models import Customer
from shipments.models import Shipment
from billing.models import Invoice
from billing.forms import InvoiceForm


def make_customer():
    return Customer.objects.create(
        name='PT Test', phone='08123456789', address='Jl. Test No. 1', city='Jakarta',
    )


def make_shipment(customer, awb, status='PICKUP', user=None):
    return Shipment.objects.create(
        awb_number=awb,
        customer=customer,
        sender_name='Pengirim', sender_phone='08111', sender_address='Jl. A',
        origin_city='Jakarta',
        recipient_name='Penerima', recipient_phone='08222', recipient_address='Jl. B',
        destination_city='Surabaya',
        service_type='REG',
        weight_kg=Decimal('2.0'),
        shipping_cost=Decimal('16000'),
        ppn_amount=Decimal('1760'),
        total_cost=Decimal('17760'),
        status=status,
        input_by=user,
    )


class InvoiceFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('finance_test', password='pass')
        self.customer = make_customer()
        self.eligible = make_shipment(self.customer, 'AWB-001', status='PICKUP')
        self.pending  = make_shipment(self.customer, 'AWB-002', status='PENDING')

    def test_pending_shipment_excluded(self):
        form = InvoiceForm()
        qs = form.fields['shipment'].queryset
        self.assertNotIn(self.pending, qs)

    def test_eligible_shipment_included(self):
        form = InvoiceForm()
        qs = form.fields['shipment'].queryset
        self.assertIn(self.eligible, qs)

    def test_invoiced_shipment_excluded(self):
        Invoice.objects.create(
            shipment=self.eligible, customer=self.customer,
            subtotal=Decimal('16000'), ppn_rate=Decimal('11.00'),
            ppn_amount=Decimal('1760'), total_amount=Decimal('17760'),
            due_date=datetime.date.today(), issued_by=self.user,
        )
        form = InvoiceForm()
        qs = form.fields['shipment'].queryset
        self.assertNotIn(self.eligible, qs)

    def test_valid_form(self):
        form = InvoiceForm(data={
            'shipment': self.eligible.pk,
            'due_date': (datetime.date.today() + datetime.timedelta(days=14)).isoformat(),
            'notes': '',
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_missing_shipment_invalid(self):
        form = InvoiceForm(data={
            'shipment': '',
            'due_date': datetime.date.today().isoformat(),
            'notes': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('shipment', form.errors)


class InvoiceCreateViewTest(TestCase):
    def setUp(self):
        finance_group = Group.objects.create(name='FINANCE')
        self.finance_user = User.objects.create_user('finance_view', password='pass')
        self.finance_user.groups.add(finance_group)
        self.other_user = User.objects.create_user('other_view', password='pass')
        self.customer = make_customer()
        self.shipment = make_shipment(self.customer, 'AWB-VIEW-001', user=self.finance_user)

    def test_unauthenticated_redirects(self):
        response = self.client.get(reverse('invoice_create'))
        self.assertEqual(response.status_code, 302)

    def test_non_finance_gets_403(self):
        self.client.login(username='other_view', password='pass')
        response = self.client.get(reverse('invoice_create'))
        self.assertEqual(response.status_code, 403)

    def test_finance_gets_200(self):
        self.client.login(username='finance_view', password='pass')
        response = self.client.get(reverse('invoice_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'billing/invoice_create.html')

    def test_context_has_shipments_data_json(self):
        self.client.login(username='finance_view', password='pass')
        response = self.client.get(reverse('invoice_create'))
        self.assertIn('shipments_data', response.context)
        import json
        data = json.loads(response.context['shipments_data'])
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['awb'], 'AWB-VIEW-001')

    def test_post_creates_invoice(self):
        self.client.login(username='finance_view', password='pass')
        self.client.post(reverse('invoice_create'), {
            'shipment': self.shipment.pk,
            'due_date': (datetime.date.today() + datetime.timedelta(days=14)).isoformat(),
            'notes': 'created via test',
        })
        self.assertEqual(Invoice.objects.count(), 1)
        inv = Invoice.objects.first()
        self.assertEqual(inv.subtotal, Decimal('16000'))
        self.assertEqual(inv.ppn_amount, Decimal('1760'))
        self.assertEqual(inv.total_amount, Decimal('17760'))
        self.assertEqual(inv.customer, self.customer)
        self.assertEqual(inv.issued_by, self.finance_user)
        self.assertEqual(inv.notes, 'created via test')

    def test_post_redirects_to_invoice_detail(self):
        self.client.login(username='finance_view', password='pass')
        response = self.client.post(reverse('invoice_create'), {
            'shipment': self.shipment.pk,
            'due_date': (datetime.date.today() + datetime.timedelta(days=14)).isoformat(),
            'notes': '',
        })
        inv = Invoice.objects.first()
        self.assertRedirects(response, reverse('invoice_detail', kwargs={'pk': inv.pk}))

    def test_post_invalid_rerenders_form(self):
        self.client.login(username='finance_view', password='pass')
        response = self.client.post(reverse('invoice_create'), {
            'shipment': '',
            'due_date': '',
            'notes': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'billing/invoice_create.html')
