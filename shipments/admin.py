from django.contrib import admin
from .models import Shipment

@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ('awb_number', 'customer', 'origin_city', 'destination_city', 'service_type', 'status', 'total_cost', 'created_at')
    search_fields = ('awb_number', 'customer__name', 'sender_name', 'recipient_name')
    list_filter = ('status', 'service_type', 'origin_city', 'destination_city')
