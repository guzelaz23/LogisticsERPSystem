from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, datetime
from customers.models import Customer
from shipments.models import Shipment
from billing.models import Invoice, Payment
from general_ledger.models import JournalEntry
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Seed January–May 2026 transaction data'

    def handle(self, *args, **kwargs):
        if Shipment.objects.filter(awb_number__startswith='AWB-2026').exists():
            self.stdout.write(self.style.WARNING('2026 data already exists. Skipping.'))
            return

        try:
            ops_user     = User.objects.get(username='ops_user')
            finance_user = User.objects.get(username='finance_user')
            c = {i: Customer.objects.get(customer_code=f'CUST-000{i}') for i in range(1, 6)}
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Run seed_data first! ({e})'))
            return

        def dt(d):
            return datetime(d.year, d.month, d.day, 8, 0, 0, tzinfo=timezone.utc)

        def ship(awb, cust, sn, sp, sa, orig, rn, rp, ra, dest, svc, wt, l, w, h, cost, ppn, total, status, d):
            s = Shipment.objects.create(
                awb_number=awb, customer=c[cust],
                sender_name=sn, sender_phone=sp, sender_address=sa, origin_city=orig,
                recipient_name=rn, recipient_phone=rp, recipient_address=ra, destination_city=dest,
                service_type=svc, weight_kg=wt, length_cm=l, width_cm=w, height_cm=h,
                shipping_cost=cost, ppn_amount=ppn, total_cost=total,
                status=status, input_by=ops_user,
            )
            Shipment.objects.filter(pk=s.pk).update(created_at=dt(d))
            return s

        def inv(inv_no, s, subtotal, ppn_amt, total, status, inv_date, due_date):
            i = Invoice.objects.create(
                invoice_number=inv_no, shipment=s, customer=s.customer,
                subtotal=subtotal, ppn_rate=11.00, ppn_amount=ppn_amt,
                total_amount=total, payment_status=status,
                due_date=due_date, issued_by=finance_user,
            )
            Invoice.objects.filter(pk=i.pk).update(created_at=dt(inv_date))
            JournalEntry.objects.filter(
                reference=inv_no, description__startswith='Invoice issued:'
            ).update(entry_date=inv_date)
            return i

        def pay(pay_no, invoice, amount, method, pay_date, ref=''):
            p = Payment.objects.create(
                payment_number=pay_no, invoice=invoice,
                amount_paid=amount, payment_method=method,
                payment_date=pay_date, bank_reference=ref,
                confirmed_by=finance_user,
            )
            Payment.objects.filter(pk=p.pk).update(created_at=dt(pay_date))
            return p

        # ── JANUARY 2026 ──────────────────────────────────────────────
        self.stdout.write('Seeding January 2026...')
        s0101 = ship('AWB-202601-000001',1,'Budi Hartono','081234567890','Jl. Sudirman No. 45','Jakarta','Maya Putri','082333444555','Jl. Pemuda No. 30','Surabaya','EXP',3.0,25,20,15,45000,4950,49950,'DELIVERED',date(2026,1,5))
        s0102 = ship('AWB-202601-000002',2,'Siti Rahayu','082345678901','Jl. Darmo No. 12','Surabaya','Hendra Gunawan','081444555666','Jl. Braga No. 22','Bandung','REG',5.0,30,25,20,40000,4400,44400,'DELIVERED',date(2026,1,7))
        s0103 = ship('AWB-202601-000003',3,'Andi Wijaya','083456789012','Jl. Braga No. 8','Bandung','Rizky Pratama','085666777888','Jl. Gajah Mada No. 10','Jakarta','SDS',1.5,20,15,10,37500,4125,41625,'DELIVERED',date(2026,1,10))
        s0104 = ship('AWB-202601-000004',4,'Dewi Lestari','084567890123','Jl. Diponegoro No. 33','Semarang','Fajar Nugroho','082777888999','Jl. Pahlawan No. 5','Yogyakarta','REG',8.0,40,30,25,64000,7040,71040,'DELIVERED',date(2026,1,12))
        s0105 = ship('AWB-202601-000005',1,'Budi Hartono','081234567890','Jl. Sudirman No. 45','Jakarta','Dian Safitri','081888999000','Jl. Kaliurang No. 8','Yogyakarta','EXP',2.5,20,15,12,37500,4125,41625,'DELIVERED',date(2026,1,15))
        s0106 = ship('AWB-202601-000006',5,'Riko Santoso','085678901234','Jl. Asia Afrika No. 7','Medan','Tania Kusuma','083999000111','Jl. Thamrin No. 45','Jakarta','CAR',30.0,60,50,40,90000,9900,99900,'DELIVERED',date(2026,1,18))
        s0107 = ship('AWB-202601-000007',2,'Siti Rahayu','082345678901','Jl. Darmo No. 12','Surabaya','Bayu Setiawan','082111333444','Jl. Tentara Pelajar No. 3','Makassar','REG',4.0,30,20,15,32000,3520,35520,'DELIVERED',date(2026,1,20))
        s0108 = ship('AWB-202601-000008',3,'Andi Wijaya','083456789012','Jl. Braga No. 8','Bandung','Nadia Permata','081222333444','Jl. Pemuda No. 18','Surabaya','EXP',3.5,25,20,15,52500,5775,58275,'DELIVERED',date(2026,1,23))

        i0101 = inv('INV-202601-000001',s0101,45000,4950,49950,'PAID',date(2026,1,6),date(2026,1,20))
        i0102 = inv('INV-202601-000002',s0102,40000,4400,44400,'PAID',date(2026,1,8),date(2026,1,22))
        i0103 = inv('INV-202601-000003',s0103,37500,4125,41625,'PAID',date(2026,1,11),date(2026,1,25))
        i0104 = inv('INV-202601-000004',s0104,64000,7040,71040,'PAID',date(2026,1,13),date(2026,1,27))
        i0105 = inv('INV-202601-000005',s0105,37500,4125,41625,'PAID',date(2026,1,16),date(2026,1,30))
        i0106 = inv('INV-202601-000006',s0106,90000,9900,99900,'PAID',date(2026,1,19),date(2026,2,2))
        i0107 = inv('INV-202601-000007',s0107,32000,3520,35520,'PAID',date(2026,1,21),date(2026,2,4))

        pay('PAY-202601-000001',i0101,49950,'TRANSFER',date(2026,1,15),'TRF-BCA-20260115-001')
        pay('PAY-202601-000002',i0102,44400,'QRIS',    date(2026,1,18),'QRIS-20260118-002')
        pay('PAY-202601-000003',i0103,41625,'CASH',    date(2026,1,20))
        pay('PAY-202601-000004',i0104,71040,'TRANSFER',date(2026,1,22),'TRF-BNI-20260122-004')
        pay('PAY-202601-000005',i0105,41625,'TRANSFER',date(2026,1,25),'TRF-BCA-20260125-005')
        pay('PAY-202601-000006',i0106,99900,'TRANSFER',date(2026,1,28),'TRF-BNI-20260128-006')
        pay('PAY-202601-000007',i0107,35520,'QRIS',    date(2026,1,28),'QRIS-20260128-007')
        self.stdout.write(self.style.SUCCESS('  ✓ January  — 8 shipments, 7 invoices, 7 paid'))

        # ── FEBRUARY 2026 ─────────────────────────────────────────────
        self.stdout.write('Seeding February 2026...')
        s0201 = ship('AWB-202602-000001',1,'Budi Hartono','081234567890','Jl. Sudirman No. 45','Jakarta','Kevin Santoso','082444555666','Jl. Pemuda No. 8','Surabaya','EXP',4.0,28,22,18,60000,6600,66600,'DELIVERED',date(2026,2,3))
        s0202 = ship('AWB-202602-000002',3,'Andi Wijaya','083456789012','Jl. Braga No. 8','Bandung','Laras Wulandari','081555666777','Jl. Malioboro No. 20','Yogyakarta','REG',6.0,35,28,22,48000,5280,53280,'DELIVERED',date(2026,2,5))
        s0203 = ship('AWB-202602-000003',4,'Dewi Lestari','084567890123','Jl. Diponegoro No. 33','Semarang','Ahmad Fauzi','083666777888','Jl. Ahmad Yani No. 30','Surabaya','SDS',2.0,22,18,12,50000,5500,55500,'DELIVERED',date(2026,2,7))
        s0204 = ship('AWB-202602-000004',2,'Siti Rahayu','082345678901','Jl. Darmo No. 12','Surabaya','Putri Handayani','082777888999','Jl. Sudirman No. 50','Jakarta','EXP',3.0,25,20,15,45000,4950,49950,'DELIVERED',date(2026,2,10))
        s0205 = ship('AWB-202602-000005',5,'Riko Santoso','085678901234','Jl. Asia Afrika No. 7','Medan','Irfan Hakim','081888999000','Jl. Kuta Raya No. 12','Bali','CAR',20.0,55,45,35,60000,6600,66600,'DELIVERED',date(2026,2,12))
        s0206 = ship('AWB-202602-000006',1,'Budi Hartono','081234567890','Jl. Sudirman No. 45','Jakarta','Ayu Pertiwi','083999000111','Jl. Diponegoro No. 15','Semarang','REG',7.5,38,30,25,60000,6600,66600,'DELIVERED',date(2026,2,15))
        s0207 = ship('AWB-202602-000007',3,'Andi Wijaya','083456789012','Jl. Braga No. 8','Bandung','Wahyu Hidayat','082111222333','Jl. Asia Afrika No. 25','Medan','EXP',5.0,30,25,20,75000,8250,83250,'DELIVERED',date(2026,2,18))
        s0208 = ship('AWB-202602-000008',4,'Dewi Lestari','084567890123','Jl. Diponegoro No. 33','Jakarta','Rina Marlina','084333444555','Jl. Gatot Subroto No. 35','Makassar','REG',4.5,30,25,20,36000,3960,39960,'DELIVERED',date(2026,2,20))
        s0209 = ship('AWB-202602-000009',2,'Siti Rahayu','082345678901','Jl. Darmo No. 12','Surabaya','Galih Pratama','081444555666','Jl. Dago No. 8','Bandung','SDS',1.5,18,15,12,37500,4125,41625,'DELIVERED',date(2026,2,23))

        i0201 = inv('INV-202602-000001',s0201,60000,6600,66600,'PAID',date(2026,2,4),date(2026,2,18))
        i0202 = inv('INV-202602-000002',s0202,48000,5280,53280,'PAID',date(2026,2,6),date(2026,2,20))
        i0203 = inv('INV-202602-000003',s0203,50000,5500,55500,'PAID',date(2026,2,8),date(2026,2,22))
        i0204 = inv('INV-202602-000004',s0204,45000,4950,49950,'PAID',date(2026,2,11),date(2026,2,25))
        i0205 = inv('INV-202602-000005',s0205,60000,6600,66600,'PAID',date(2026,2,13),date(2026,2,27))
        i0206 = inv('INV-202602-000006',s0206,60000,6600,66600,'PAID',date(2026,2,16),date(2026,3,2))
        i0207 = inv('INV-202602-000007',s0207,75000,8250,83250,'PAID',date(2026,2,19),date(2026,3,5))
        i0208 = inv('INV-202602-000008',s0208,36000,3960,39960,'PAID',date(2026,2,21),date(2026,3,7))

        pay('PAY-202602-000001',i0201,66600,'TRANSFER',date(2026,2,12),'TRF-BCA-20260212-001')
        pay('PAY-202602-000002',i0202,53280,'QRIS',    date(2026,2,14),'QRIS-20260214-002')
        pay('PAY-202602-000003',i0203,55500,'CASH',    date(2026,2,16))
        pay('PAY-202602-000004',i0204,49950,'TRANSFER',date(2026,2,20),'TRF-BNI-20260220-004')
        pay('PAY-202602-000005',i0205,66600,'TRANSFER',date(2026,2,22),'TRF-BCA-20260222-005')
        pay('PAY-202602-000006',i0206,66600,'TRANSFER',date(2026,2,25),'TRF-BCA-20260225-006')
        pay('PAY-202602-000007',i0207,83250,'QRIS',    date(2026,2,25),'QRIS-20260225-007')
        pay('PAY-202602-000008',i0208,39960,'CASH',    date(2026,2,28))
        self.stdout.write(self.style.SUCCESS('  ✓ February — 9 shipments, 8 invoices, 8 paid'))

        # ── MARCH 2026 ────────────────────────────────────────────────
        self.stdout.write('Seeding March 2026...')
        s0301 = ship('AWB-202603-000001',1,'Budi Hartono','081234567890','Jl. Sudirman No. 45','Jakarta','Citra Dewi','082555666777','Jl. Ahmad Yani No. 10','Surabaya','EXP',4.5,28,22,18,67500,7425,74925,'DELIVERED',date(2026,3,3))
        s0302 = ship('AWB-202603-000002',2,'Siti Rahayu','082345678901','Jl. Darmo No. 12','Surabaya','Doni Pramana','081666777888','Jl. Braga No. 35','Bandung','REG',7.0,38,30,25,56000,6160,62160,'DELIVERED',date(2026,3,5))
        s0303 = ship('AWB-202603-000003',3,'Andi Wijaya','083456789012','Jl. Braga No. 8','Bandung','Elsa Kurniawan','083777888999','Jl. Malioboro No. 5','Yogyakarta','SDS',2.5,22,18,15,62500,6875,69375,'DELIVERED',date(2026,3,7))
        s0304 = ship('AWB-202603-000004',4,'Dewi Lestari','084567890123','Jl. Diponegoro No. 33','Semarang','Faisal Ramadan','082888999000','Jl. Imam Bonjol No. 20','Medan','CAR',35.0,70,50,45,105000,11550,116550,'DELIVERED',date(2026,3,10))
        s0305 = ship('AWB-202603-000005',5,'Riko Santoso','085678901234','Jl. Asia Afrika No. 7','Jakarta','Grace Natalia','081999000111','Jl. Pemuda No. 15','Surabaya','EXP',3.5,25,20,15,52500,5775,58275,'DELIVERED',date(2026,3,12))
        s0306 = ship('AWB-202603-000006',1,'Budi Hartono','081234567890','Jl. Sudirman No. 45','Jakarta','Hadi Santoso','083111222333','Jl. Diponegoro No. 8','Semarang','REG',5.5,32,28,22,44000,4840,48840,'DELIVERED',date(2026,3,15))
        s0307 = ship('AWB-202603-000007',2,'Siti Rahayu','082345678901','Jl. Darmo No. 12','Surabaya','Indra Gunawan','084222333444','Jl. Kuta Raya No. 3','Bali','EXP',4.0,28,22,18,60000,6600,66600,'DELIVERED',date(2026,3,18))
        s0308 = ship('AWB-202603-000008',3,'Andi Wijaya','083456789012','Jl. Braga No. 8','Bandung','Jasmine Putri','082333444555','Jl. Thamrin No. 10','Jakarta','REG',6.5,35,28,22,52000,5720,57720,'DELIVERED',date(2026,3,20))
        s0309 = ship('AWB-202603-000009',4,'Dewi Lestari','084567890123','Jl. Diponegoro No. 33','Semarang','Kartika Sari','081444555666','Jl. Ahmad Yani No. 25','Surabaya','SDS',1.8,20,16,12,45000,4950,49950,'DELIVERED',date(2026,3,22))
        s0310 = ship('AWB-202603-000010',5,'Riko Santoso','085678901234','Jl. Asia Afrika No. 7','Medan','Lina Marlina','083555666777','Jl. Gatot Subroto No. 8','Jakarta','REG',9.0,42,35,28,72000,7920,79920,'DELIVERED',date(2026,3,25))

        i0301 = inv('INV-202603-000001',s0301,67500,7425,74925,'PAID',date(2026,3,4),date(2026,3,18))
        i0302 = inv('INV-202603-000002',s0302,56000,6160,62160,'PAID',date(2026,3,6),date(2026,3,20))
        i0303 = inv('INV-202603-000003',s0303,62500,6875,69375,'PAID',date(2026,3,8),date(2026,3,22))
        i0304 = inv('INV-202603-000004',s0304,105000,11550,116550,'PAID',date(2026,3,11),date(2026,3,25))
        i0305 = inv('INV-202603-000005',s0305,52500,5775,58275,'PAID',date(2026,3,13),date(2026,3,27))
        i0306 = inv('INV-202603-000006',s0306,44000,4840,48840,'PAID',date(2026,3,16),date(2026,3,30))
        i0307 = inv('INV-202603-000007',s0307,60000,6600,66600,'PAID',date(2026,3,19),date(2026,4,2))
        i0308 = inv('INV-202603-000008',s0308,52000,5720,57720,'PAID',date(2026,3,21),date(2026,4,4))
        i0309 = inv('INV-202603-000009',s0309,45000,4950,49950,'PAID',date(2026,3,23),date(2026,4,6))

        pay('PAY-202603-000001',i0301,74925,'TRANSFER',date(2026,3,12),'TRF-BCA-20260312-001')
        pay('PAY-202603-000002',i0302,62160,'QRIS',    date(2026,3,14),'QRIS-20260314-002')
        pay('PAY-202603-000003',i0303,69375,'CASH',    date(2026,3,16))
        pay('PAY-202603-000004',i0304,116550,'TRANSFER',date(2026,3,20),'TRF-BNI-20260320-004')
        pay('PAY-202603-000005',i0305,58275,'TRANSFER',date(2026,3,22),'TRF-BCA-20260322-005')
        pay('PAY-202603-000006',i0306,48840,'QRIS',    date(2026,3,25),'QRIS-20260325-006')
        pay('PAY-202603-000007',i0307,66600,'TRANSFER',date(2026,3,28),'TRF-BCA-20260328-007')
        pay('PAY-202603-000008',i0308,57720,'CASH',    date(2026,3,30))
        pay('PAY-202603-000009',i0309,49950,'TRANSFER',date(2026,4,1),'TRF-BNI-20260401-009')
        self.stdout.write(self.style.SUCCESS('  ✓ March    — 10 shipments, 9 invoices, 9 paid'))

        # ── APRIL 2026 ────────────────────────────────────────────────
        self.stdout.write('Seeding April 2026...')
        s0401 = ship('AWB-202604-000001',1,'Budi Hartono','081234567890','Jl. Sudirman No. 45','Jakarta','Mira Susanti','082666777888','Jl. Pemuda No. 42','Surabaya','EXP',5.0,30,25,20,75000,8250,83250,'DELIVERED',date(2026,4,2))
        s0402 = ship('AWB-202604-000002',2,'Siti Rahayu','082345678901','Jl. Darmo No. 12','Surabaya','Nanda Pratiwi','081777888999','Jl. Braga No. 15','Bandung','REG',4.0,28,22,18,32000,3520,35520,'DELIVERED',date(2026,4,5))
        s0403 = ship('AWB-202604-000003',3,'Andi Wijaya','083456789012','Jl. Braga No. 8','Bandung','Oscar Perdana','083888999000','Jl. Kaliurang No. 20','Yogyakarta','SDS',2.0,20,16,12,50000,5500,55500,'DELIVERED',date(2026,4,7))
        s0404 = ship('AWB-202604-000004',4,'Dewi Lestari','084567890123','Jl. Diponegoro No. 33','Semarang','Pandu Wijaya','082999000111','Jl. Imam Bonjol No. 8','Medan','CAR',25.0,60,50,40,75000,8250,83250,'DELIVERED',date(2026,4,10))
        s0405 = ship('AWB-202604-000005',5,'Riko Santoso','085678901234','Jl. Asia Afrika No. 7','Medan','Qory Indah','081000111222','Jl. Thamrin No. 20','Jakarta','EXP',3.5,25,20,15,52500,5775,58275,'DELIVERED',date(2026,4,12))
        s0406 = ship('AWB-202604-000006',1,'Budi Hartono','081234567890','Jl. Sudirman No. 45','Jakarta','Ratna Dewi','083111222333','Jl. Diponegoro No. 25','Semarang','REG',6.0,35,28,22,48000,5280,53280,'DELIVERED',date(2026,4,15))
        s0407 = ship('AWB-202604-000007',2,'Siti Rahayu','082345678901','Jl. Darmo No. 12','Surabaya','Surya Kusuma','084444555666','Jl. Sudirman No. 30','Jakarta','EXP',4.5,28,22,18,67500,7425,74925,'DELIVERED',date(2026,4,18))
        s0408 = ship('AWB-202604-000008',3,'Andi Wijaya','083456789012','Jl. Braga No. 8','Bandung','Tari Lestari','082555666777','Jl. Gatot Subroto No. 15','Makassar','REG',8.0,40,32,25,64000,7040,71040,'DELIVERED',date(2026,4,20))

        i0401 = inv('INV-202604-000001',s0401,75000,8250,83250,'PAID',date(2026,4,3),date(2026,4,17))
        i0402 = inv('INV-202604-000002',s0402,32000,3520,35520,'PAID',date(2026,4,6),date(2026,4,20))
        i0403 = inv('INV-202604-000003',s0403,50000,5500,55500,'PAID',date(2026,4,8),date(2026,4,22))
        i0404 = inv('INV-202604-000004',s0404,75000,8250,83250,'PAID',date(2026,4,11),date(2026,4,25))
        i0405 = inv('INV-202604-000005',s0405,52500,5775,58275,'PAID',date(2026,4,13),date(2026,4,27))
        i0406 = inv('INV-202604-000006',s0406,48000,5280,53280,'PAID',date(2026,4,16),date(2026,4,30))
        i0407 = inv('INV-202604-000007',s0407,67500,7425,74925,'OVERDUE',date(2026,4,19),date(2026,5,3))

        pay('PAY-202604-000001',i0401,83250,'TRANSFER',date(2026,4,10),'TRF-BCA-20260410-001')
        pay('PAY-202604-000002',i0402,35520,'CASH',    date(2026,4,15))
        pay('PAY-202604-000003',i0403,55500,'QRIS',    date(2026,4,17),'QRIS-20260417-003')
        pay('PAY-202604-000004',i0404,83250,'TRANSFER',date(2026,4,20),'TRF-BNI-20260420-004')
        pay('PAY-202604-000005',i0405,58275,'TRANSFER',date(2026,4,22),'TRF-BCA-20260422-005')
        pay('PAY-202604-000006',i0406,53280,'QRIS',    date(2026,4,25),'QRIS-20260425-006')
        self.stdout.write(self.style.SUCCESS('  ✓ April    — 8 shipments, 7 invoices, 6 paid, 1 overdue'))

        # ── MAY 2026 ──────────────────────────────────────────────────
        self.stdout.write('Seeding May 2026...')
        s0501 = ship('AWB-202605-000001',1,'Budi Hartono','081234567890','Jl. Sudirman No. 45','Jakarta','Umi Kalsum','082777888999','Jl. Pemuda No. 55','Surabaya','EXP',4.0,28,22,18,60000,6600,66600,'DELIVERED',date(2026,5,2))
        s0502 = ship('AWB-202605-000002',2,'Siti Rahayu','082345678901','Jl. Darmo No. 12','Surabaya','Vino Bastian','081888999000','Jl. Braga No. 42','Bandung','REG',5.0,30,25,20,40000,4400,44400,'DELIVERED',date(2026,5,5))
        s0503 = ship('AWB-202605-000003',3,'Andi Wijaya','083456789012','Jl. Braga No. 8','Bandung','Wulan Pratiwi','083999000111','Jl. Kaliurang No. 35','Yogyakarta','SDS',2.5,22,18,15,62500,6875,69375,'DELIVERED',date(2026,5,7))
        s0504 = ship('AWB-202605-000004',4,'Dewi Lestari','084567890123','Jl. Diponegoro No. 33','Semarang','Xander Hartono','082000111222','Jl. Imam Bonjol No. 15','Medan','CAR',28.0,65,50,42,84000,9240,93240,'DELIVERED',date(2026,5,9))
        s0505 = ship('AWB-202605-000005',5,'Riko Santoso','085678901234','Jl. Asia Afrika No. 7','Medan','Yuni Shara','081111222333','Jl. Sudirman No. 85','Jakarta','EXP',3.0,25,20,15,45000,4950,49950,'TRANSIT',date(2026,5,12))
        s0506 = ship('AWB-202605-000006',1,'Budi Hartono','081234567890','Jl. Sudirman No. 45','Jakarta','Zahra Aulia','083222333444','Jl. Diponegoro No. 40','Semarang','REG',7.0,38,30,25,56000,6160,62160,'PICKUP',date(2026,5,15))
        s0507 = ship('AWB-202605-000007',2,'Siti Rahayu','082345678901','Jl. Darmo No. 12','Surabaya','Arif Rahman','084555666777','Jl. Gatot Subroto No. 22','Makassar','EXP',4.5,28,22,18,67500,7425,74925,'PENDING',date(2026,5,17))

        # Only DELIVERED shipments get invoiced
        i0501 = inv('INV-202605-000001',s0501,60000,6600,66600,'PAID',  date(2026,5,3), date(2026,5,17))
        i0502 = inv('INV-202605-000002',s0502,40000,4400,44400,'PAID',  date(2026,5,6), date(2026,5,20))
        i0503 = inv('INV-202605-000003',s0503,62500,6875,69375,'PAID',  date(2026,5,8), date(2026,5,22))
        i0504 = inv('INV-202605-000004',s0504,84000,9240,93240,'UNPAID',date(2026,5,10),date(2026,5,24))

        pay('PAY-202605-000001',i0501,66600,'TRANSFER',date(2026,5,10),'TRF-BCA-20260510-001')
        pay('PAY-202605-000002',i0502,44400,'CASH',    date(2026,5,12))
        pay('PAY-202605-000003',i0503,69375,'QRIS',    date(2026,5,14),'QRIS-20260514-003')
        self.stdout.write(self.style.SUCCESS('  ✓ May      — 7 shipments, 4 invoices, 3 paid, 1 unpaid, 3 in transit/pickup/pending'))

        self.stdout.write(self.style.SUCCESS('\n✅ 2026 seed complete!'))
        self.stdout.write('   Total: 42 shipments | 35 invoices | 33 payments')
        self.stdout.write('   Run: python manage.py seed_2026')
