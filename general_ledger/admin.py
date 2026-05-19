from django.contrib import admin
from .models import ChartOfAccount, JournalEntry, JournalEntryLine, GeneralLedger


class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 2


@admin.register(ChartOfAccount)
class CoAAdmin(admin.ModelAdmin):
    list_display  = ['account_code', 'account_name', 'account_type', 'normal_balance', 'is_active']
    list_filter   = ['account_type', 'is_active']
    search_fields = ['account_code', 'account_name']


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display    = ['entry_number', 'entry_date', 'description', 'reference', 'is_posted']
    list_filter     = ['is_posted', 'entry_date']
    search_fields   = ['entry_number', 'reference']
    readonly_fields = ['entry_number', 'created_at']
    inlines         = [JournalEntryLineInline]


@admin.register(GeneralLedger)
class GLAdmin(admin.ModelAdmin):
    list_display    = ['account', 'debit_total', 'credit_total', 'last_updated']
    readonly_fields = ['last_updated']
