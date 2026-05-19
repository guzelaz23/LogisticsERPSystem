import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from customers.models import Customer
from shipments.models import Shipment
from billing.models import Invoice, Payment
from django.utils import timezone
from datetime import date, timedelta

class Command(BaseCommand):
    help = 'Seed database with dummy data for SAP Express ERP'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting seed data...')

        # ─── GROUPS & USERS ───────────────────────────────────
        sales_ops, _ = Group.objects.get_or_create(name='SALES_OPS')
        finance,   _ = Group.objects.get_or_create(name='FINANCE')
        mgmt,      _ = Group.objects.get_or_create(name='MANAGEMENT')

        ops_user, created = User.objects.get_or_create(username='ops_user')
        if created:
            ops_user.set_password('ops123')
            ops_user.save()
        ops_user.groups.set([sales_ops])

        finance_user, created = User.objects.get_or_create(username='finance_user')
        if created:
            finance_user.set_password('finance123')
            finance_user.save()
        finance_user.groups.set([finance])

        mgmt_user, created = User.objects.get_or_create(username='mgmt_user')
        if created:
            mgmt_user.set_password('mgmt123')
            mgmt_user.save()
        mgmt_user.groups.set([mgmt])

        self.stdout.write(self.style.SUCCESS('✓ Groups and users created!'))

        # ─── CUSTOMERS ────────────────────────────────────────
        if not Customer.objects.exists():
            customers_data = [
                {'customer_code': 'CUST-0001', 'name': 'Budi Hartono',  'company': 'PT Maju Bersama',  'phone': '081234567890', 'email': 'budi@majubersama.co.id',   'address': 'Jl. Sudirman No. 45',    'city': 'Jakarta'},
                {'customer_code': 'CUST-0002', 'name': 'Siti Rahayu',   'company': 'Toko Berkah',       'phone': '082345678901', 'email': 'siti@tokoberkah.com',      'address': 'Jl. Darmo No. 12',       'city': 'Surabaya'},
                {'customer_code': 'CUST-0003', 'name': 'Andi Wijaya',   'company': 'CV Sinar Jaya',     'phone': '083456789012', 'email': 'andi@sinarjaya.com',       'address': 'Jl. Braga No. 8',        'city': 'Bandung'},
                {'customer_code': 'CUST-0004', 'name': 'Dewi Lestari',  'company': 'PT Indo Logistik',  'phone': '084567890123', 'email': 'dewi@indologistik.co.id',  'address': 'Jl. Diponegoro No. 33',  'city': 'Semarang'},
                {'customer_code': 'CUST-0005', 'name': 'Riko Santoso',  'company': '',                  'phone': '085678901234', 'email': 'riko.santoso@gmail.com',   'address': 'Jl. Asia Afrika No. 7',  'city': 'Medan'},
            ]
            for c in customers_data:
                Customer.objects.create(**c)
            self.stdout.write(self.style.SUCCESS('✓ Customers created!'))
        else:
            self.stdout.write('  Customers already exist, skipping...')

        # ─── SHIPMENTS ────────────────────────────────────────
        if not Shipment.objects.exists():
            c1 = Customer.objects.get(customer_code='CUST-0001')
            c2 = Customer.objects.get(customer_code='CUST-0002')
            c3 = Customer.objects.get(customer_code='CUST-0003')
            c4 = Customer.objects.get(customer_code='CUST-0004')
            c5 = Customer.objects.get(customer_code='CUST-0005')

            shipments_data = [
                # AWB, customer, sender_name, sender_phone, sender_address, origin,
                # recipient_name, recipient_phone, recipient_address, destination,
                # service, weight, l, w, h, shipping_cost, ppn, total, status
                ('AWB-202412-000001', c1, 'Budi Hartono',  '081234567890', 'Jl. Sudirman No. 45',    'Jakarta',
                 'Rina Kusuma',      '082111222333', 'Jl. Pemuda No. 10',          'Surabaya',
                 'EXP', 5.00,  30, 20, 15,  75000, 8250,  83250,  'DELIVERED'),

                ('AWB-202412-000002', c3, 'Andi Wijaya',   '083456789012', 'Jl. Braga No. 8',        'Bandung',
                 'Made Sukma',       '081333444555', 'Jl. Kuta Raya No. 5',        'Bali',
                 'REG', 2.50,  25, 15, 10,  20000, 2200,  22200,  'TRANSIT'),

                ('AWB-202412-000003', c1, 'Budi Hartono',  '081234567890', 'Jl. Sudirman No. 45',    'Jakarta',
                 'Ahmad Fuad',       '085999888777', 'Jl. Gatot Subroto No. 22',   'Medan',
                 'CAR', 25.00, 60, 40, 40,  75000, 8250,  83250,  'DELIVERED'),

                ('AWB-202412-000004', c2, 'Siti Rahayu',   '082345678901', 'Jl. Darmo No. 12',       'Surabaya',
                 'Bagas Prabowo',    '081555666777', 'Jl. Perintis Kemerdekaan 9', 'Makassar',
                 'REG', 3.00,  20, 15, 10,  24000, 2640,  26640,  'PENDING'),

                ('AWB-202412-000005', c4, 'Dewi Lestari',  '084567890123', 'Jl. Diponegoro No. 33',  'Jakarta',
                 'Yoga Pratama',     '082666777888', 'Jl. Malioboro No. 15',       'Yogyakarta',
                 'SDS', 1.00,  15, 10, 10,  25000, 2750,  27750,  'DELIVERED'),

                ('AWB-202412-000006', c4, 'Dewi Lestari',  '084567890123', 'Jl. Diponegoro No. 33',  'Semarang',
                 'Tommy Kurniawan',  '083777888999', 'Jl. Thamrin No. 20',         'Jakarta',
                 'EXP', 4.00,  25, 20, 15,  60000, 6600,  66600,  'DELIVERED'),

                ('AWB-202412-000007', c5, 'Riko Santoso',  '085678901234', 'Jl. Asia Afrika No. 7',  'Medan',
                 'Linda Sari',       '081888999000', 'Jl. Dago No. 3',             'Bandung',
                 'REG', 1.50,  20, 15, 10,  12000, 1320,  13320,  'PICKUP'),

                ('AWB-202412-000008', c1, 'Budi Hartono',  '081234567890', 'Jl. Sudirman No. 45',    'Jakarta',
                 'Wahyu Setiawan',   '082999000111', 'Jl. Pemuda No. 25',          'Semarang',
                 'REG', 7.00,  40, 30, 20,  56000, 6160,  62160,  'DELIVERED'),

                ('AWB-202412-000009', c3, 'Andi Wijaya',   '083456789012', 'Jl. Braga No. 8',        'Bandung',
                 'Retno Wulandari',  '081000111222', 'Jl. Ahmad Yani No. 18',      'Surabaya',
                 'EXP', 6.00,  35, 25, 20,  90000, 9900,  99900,  'DELIVERED'),

                ('AWB-202412-000010', c2, 'Siti Rahayu',   '082345678901', 'Jl. Darmo No. 12',       'Surabaya',
                 'Firman Hidayat',   '083111222333', 'Jl. Sudirman No. 100',       'Jakarta',
                 'SDS', 2.00,  20, 15, 15,  50000, 5500,  55500,  'DELIVERED'),
            ]

            for d in shipments_data:
                Shipment.objects.create(
                    awb_number=d[0], customer=d[1],
                    sender_name=d[2], sender_phone=d[3],
                    sender_address=d[4], origin_city=d[5],
                    recipient_name=d[6], recipient_phone=d[7],
                    recipient_address=d[8], destination_city=d[9],
                    service_type=d[10], weight_kg=d[11],
                    length_cm=d[12], width_cm=d[13], height_cm=d[14],
                    shipping_cost=d[15], ppn_amount=d[16], total_cost=d[17],
                    status=d[18], input_by=ops_user,
                )
            self.stdout.write(self.style.SUCCESS('✓ Shipments created!'))
        else:
            self.stdout.write('  Shipments already exist, skipping...')

        # ─── INVOICES ─────────────────────────────────────────
        if not Invoice.objects.exists():
            def get_s(awb):
                return Shipment.objects.get(awb_number=awb)

            invoices_data = [
                # invoice_no, awb, subtotal, ppn, total, status, due_date
                ('INV-202412-000001', 'AWB-202412-000001', 75000, 8250,  83250, 'PAID',    date(2024,12,28)),
                ('INV-202412-000002', 'AWB-202412-000003', 75000, 8250,  83250, 'PAID',    date(2024,12,30)),
                ('INV-202412-000003', 'AWB-202412-000005', 25000, 2750,  27750, 'PAID',    date(2024,12,31)),
                ('INV-202412-000004', 'AWB-202412-000006', 60000, 6600,  66600, 'UNPAID',  date(2025, 1, 5)),
                ('INV-202412-000005', 'AWB-202412-000008', 56000, 6160,  62160, 'OVERDUE', date(2024,12,15)),
                ('INV-202412-000006', 'AWB-202412-000009', 90000, 9900,  99900, 'PAID',    date(2025, 1, 2)),
                ('INV-202412-000007', 'AWB-202412-000010', 50000, 5500,  55500, 'UNPAID',  date(2025, 1,10)),
            ]

            for inv in invoices_data:
                s = get_s(inv[1])
                Invoice.objects.create(
                    invoice_number=inv[0],
                    shipment=s,
                    customer=s.customer,
                    subtotal=inv[2],
                    ppn_rate=11.00,
                    ppn_amount=inv[3],
                    total_amount=inv[4],
                    payment_status=inv[5],
                    due_date=inv[6],
                    issued_by=finance_user,
                )
            self.stdout.write(self.style.SUCCESS('✓ Invoices created!'))
        else:
            self.stdout.write('  Invoices already exist, skipping...')

        # ─── PAYMENTS ─────────────────────────────────────────
        if not Payment.objects.exists():
            def get_inv(inv_no):
                return Invoice.objects.get(invoice_number=inv_no)

            payments_data = [
                ('PAY-202412-000001', 'INV-202412-000001', 83250, 'TRANSFER', date(2024,12,16), 'TRF-BCA-20241216-001'),
                ('PAY-202412-000002', 'INV-202412-000002', 83250, 'QRIS',     date(2024,12,18), 'QRIS-20241218-002'),
                ('PAY-202412-000003', 'INV-202412-000003', 27750, 'CASH',     date(2024,12,20), ''),
                ('PAY-202412-000004', 'INV-202412-000006', 99900, 'TRANSFER', date(2024,12,25), 'TRF-BNI-20241225-004'),
            ]

            for p in payments_data:
                Payment.objects.create(
                    payment_number=p[0],
                    invoice=get_inv(p[1]),
                    amount_paid=p[2],
                    payment_method=p[3],
                    payment_date=p[4],
                    bank_reference=p[5],
                    confirmed_by=finance_user,
                )
            self.stdout.write(self.style.SUCCESS('✓ Payments created!'))
        else:
            self.stdout.write('  Payments already exist, skipping...')

        self.stdout.write(self.style.SUCCESS('\n✅ Seed data completed!'))
        self.stdout.write('─────────────────────────────────')
        self.stdout.write('Login credentials:')
        self.stdout.write('  ops_user     / ops123')
        self.stdout.write('  finance_user / finance123')
        self.stdout.write('  mgmt_user    / mgmt123')