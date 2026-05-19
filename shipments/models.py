from django.db import models
from django.contrib.auth.models import User
from customers.models import Customer

ORIGIN_CHOICES = [
    ('Jakarta','Jakarta'), ('Surabaya','Surabaya'), ('Bandung','Bandung'),
    ('Medan','Medan'), ('Semarang','Semarang'), ('Makassar','Makassar'),
    ('Bali','Bali'), ('Yogyakarta','Yogyakarta'),
]
STATUS_CHOICES = [
    ('PENDING','Pending'), ('PICKUP','Picked Up'), ('TRANSIT','In Transit'),
    ('DELIVERED','Delivered'), ('RETURNED','Returned'),
]
SERVICE_CHOICES = [
    ('REG','Regular (3-5 hari)'), ('EXP','Express (1-2 hari)'),
    ('SDS','Same Day'), ('CAR','Cargo'),
]

class Shipment(models.Model):
    awb_number          = models.CharField(max_length=30, unique=True)
    customer            = models.ForeignKey(Customer, on_delete=models.PROTECT)
    sender_name         = models.CharField(max_length=200)
    sender_phone        = models.CharField(max_length=20)
    sender_address      = models.TextField()
    origin_city         = models.CharField(max_length=100, choices=ORIGIN_CHOICES)
    recipient_name      = models.CharField(max_length=200)
    recipient_phone     = models.CharField(max_length=20)
    recipient_address   = models.TextField()
    destination_city    = models.CharField(max_length=100, choices=ORIGIN_CHOICES)
    service_type        = models.CharField(max_length=10, choices=SERVICE_CHOICES, default='REG')
    weight_kg           = models.DecimalField(max_digits=8, decimal_places=2)
    length_cm           = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    width_cm            = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    height_cm           = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    package_description = models.TextField(blank=True)
    base_rate           = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost       = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ppn_amount          = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost          = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    input_by            = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.awb_number

    def calculate_cost(self):
        RATE_TABLE = {'REG': 8000, 'EXP': 15000, 'SDS': 25000, 'CAR': 3000}
        volumetric = (float(self.length_cm) * float(self.width_cm) * float(self.height_cm)) / 5000
        chargeable = max(float(self.weight_kg), volumetric)
        base = RATE_TABLE.get(self.service_type, 8000)
        self.base_rate    = base
        self.shipping_cost = round(chargeable * base, 2)
        self.ppn_amount    = round(self.shipping_cost * 0.11, 2)
        self.total_cost    = self.shipping_cost + self.ppn_amount
        return self.total_cost

    def save(self, *args, **kwargs):
        if not self.awb_number:
            from django.utils import timezone
            ym = timezone.now().strftime('%Y%m')
            last = Shipment.objects.filter(awb_number__startswith=f'AWB-{ym}').order_by('-awb_number').first()
            seq = 1
            if last:
                try:
                    seq = int(last.awb_number.split('-')[-1]) + 1
                except ValueError:
                    seq = 1
            self.awb_number = f"AWB-{ym}-{seq:06d}"
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']
