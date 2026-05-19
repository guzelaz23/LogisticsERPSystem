from django import forms
from .models import Shipment

class ShipmentForm(forms.ModelForm):
    class Meta:
        model = Shipment
        fields = [
            'customer', 'sender_name', 'sender_phone', 'sender_address', 'origin_city',
            'recipient_name', 'recipient_phone', 'recipient_address', 'destination_city',
            'service_type', 'weight_kg', 'length_cm', 'width_cm', 'height_cm', 'package_description'
        ]
        widgets = {
            'customer': forms.Select(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500', 'x-model': 'customerId', '@change': 'fetchCustomerDetails()'}),
            'sender_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500', 'x-model': 'senderName'}),
            'sender_phone': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500', 'x-model': 'senderPhone'}),
            'sender_address': forms.Textarea(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500', 'rows': 3, 'x-model': 'senderAddress'}),
            'origin_city': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500', 'x-model': 'originCity', 'placeholder': 'e.g. Jakarta'}),
            
            'recipient_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500'}),
            'recipient_phone': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500'}),
            'recipient_address': forms.Textarea(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500', 'rows': 3}),
            'destination_city': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500', 'placeholder': 'e.g. Surabaya'}),
            
            'service_type': forms.Select(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500', 'x-model': 'serviceType'}),
            'weight_kg': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500', 'x-model': 'weight', 'step': '0.1'}),
            'length_cm': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500', 'x-model': 'length'}),
            'width_cm': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500', 'x-model': 'width'}),
            'height_cm': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500', 'x-model': 'height'}),
            'package_description': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500'}),
        }
