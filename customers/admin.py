from django.contrib import admin
from .models import Customer

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('customer_code', 'name', 'company', 'phone', 'city', 'is_active')
    search_fields = ('customer_code', 'name', 'company', 'phone')
    list_filter = ('is_active', 'city')
