from django.urls import path
from . import views

urlpatterns = [
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/create/', views.invoice_create, name='invoice_create'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/print/', views.invoice_print, name='invoice_print'),
    path('payments/', views.payment_list, name='payment_list'),
    path('payment/confirm/', views.confirm_payment, name='confirm_payment'),
    path('payment/confirm/<int:invoice_id>/', views.confirm_payment, name='confirm_payment_id'),
    path('expense/record/', views.record_expense, name='record_expense'),
]
