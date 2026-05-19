from django.contrib import admin
from .models import Invoice, Payment

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'customer', 'shipment', 'total_amount', 'payment_status', 'due_date')
    search_fields = ('invoice_number', 'customer__name', 'shipment__awb_number')
    list_filter = ('payment_status', 'due_date')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_number', 'invoice', 'amount_paid', 'payment_method', 'payment_date')
    search_fields = ('payment_number', 'invoice__invoice_number')
    list_filter = ('payment_method', 'payment_date')
