from django.db import models

class Customer(models.Model):
    customer_code = models.CharField(max_length=20, unique=True)  # auto: CUST-0001
    name          = models.CharField(max_length=200)
    company       = models.CharField(max_length=200, blank=True)
    phone         = models.CharField(max_length=20)
    email         = models.EmailField(blank=True)
    address       = models.TextField()
    city          = models.CharField(max_length=100)
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer_code} — {self.name}"

    def save(self, *args, **kwargs):
        if not self.customer_code:
            last = Customer.objects.order_by('-id').first()
            next_id = (last.id + 1) if last else 1
            self.customer_code = f"CUST-{next_id:04d}"
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']
