from django.urls import path
from . import views

urlpatterns = [
    path('shipments/',        views.shipment_report,  name='shipment_report'),
    path('revenue/',          views.revenue_report,   name='revenue_report'),
    path('trial-balance/',    views.trial_balance,    name='trial_balance'),
    path('income-statement/', views.income_statement, name='income_statement'),
    path('balance-sheet/',    views.balance_sheet,    name='balance_sheet'),
    path('journal-entries/',  views.journal_entries,  name='journal_entries'),
    path('journal-entries/<int:pk>/delete/', views.delete_journal_entry, name='delete_journal_entry'),
    path('ar-aging/',         views.ar_aging,          name='ar_aging'),
    path('cash-flow/',        views.cash_flow_statement, name='cash_flow_statement'),
]
