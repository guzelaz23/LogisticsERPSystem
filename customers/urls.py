from django.urls import path
from . import views

urlpatterns = [
    path('', views.customer_list, name='customer_list'),
    path('add/', views.customer_add, name='customer_add'),
    path('<int:pk>/', views.customer_detail, name='customer_detail'),
    path('<int:pk>/toggle-active/', views.customer_toggle_active, name='customer_toggle_active'),
]
