from django.urls import path
from . import views

urlpatterns = [
    path('', views.coa_list, name='coa_list'),
    path('create/', views.coa_create, name='coa_create'),
    path('<int:pk>/edit/', views.coa_edit, name='coa_edit'),
]
