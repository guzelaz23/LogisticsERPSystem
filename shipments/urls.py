from django.urls import path
from . import views

urlpatterns = [
    path('', views.shipment_list, name='shipment_list'),
    path('add/', views.shipment_add, name='shipment_add'),
    path('<int:pk>/', views.shipment_detail, name='shipment_detail'),
    path('<int:pk>/edit/',   views.shipment_edit,          name='shipment_edit'),
    path('<int:pk>/status/', views.shipment_update_status, name='shipment_update_status'),
    path('<int:pk>/generate-invoice/', views.generate_invoice, name='generate_invoice'),
]
