from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from ais_finalproject.utils import group_required
from .models import Customer
from .forms import CustomerForm

@group_required('SALES_OPS', 'FINANCE', 'MANAGEMENT')
def customer_list(request):
    query = request.GET.get('q', '')
    if query:
        customers_list = Customer.objects.filter(name__icontains=query) | Customer.objects.filter(customer_code__icontains=query)
    else:
        customers_list = Customer.objects.all()

    paginator = Paginator(customers_list, 10)
    page_number = request.GET.get('page')
    customers = paginator.get_page(page_number)

    return render(request, 'customers/list.html', {'customers': customers, 'query': query})

@group_required('SALES_OPS')
def customer_add(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f"Customer created! Code: {customer.customer_code}")
            return redirect('customer_list')
    else:
        form = CustomerForm()
    
    return render(request, 'customers/add.html', {'form': form})

@group_required('SALES_OPS', 'FINANCE', 'MANAGEMENT')
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    shipments = customer.shipment_set.all()[:10]
    return render(request, 'customers/detail.html', {'customer': customer, 'shipments': shipments})

@group_required('SALES_OPS')
def customer_toggle_active(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        customer.is_active = not customer.is_active
        customer.save()
        status = "activated" if customer.is_active else "deactivated"
        messages.success(request, f"{customer.name} has been {status}.")
    return redirect('customer_detail', pk=pk)
