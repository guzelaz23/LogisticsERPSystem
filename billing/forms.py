from django import forms
from .models import Payment


class ExpenseForm(forms.Form):
    INPUT_CLASS = 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500'

    account      = forms.ChoiceField(widget=forms.Select(attrs={'class': INPUT_CLASS}))
    amount       = forms.DecimalField(max_digits=14, decimal_places=2,
                                      widget=forms.NumberInput(attrs={'class': INPUT_CLASS, 'min': '0.01'}))
    expense_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': INPUT_CLASS}))
    description  = forms.CharField(widget=forms.TextInput(attrs={'class': INPUT_CLASS}))
    reference    = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': INPUT_CLASS}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from general_ledger.models import ChartOfAccount
        expense_accounts = ChartOfAccount.objects.filter(
            account_type='EXPENSE', is_active=True
        ).order_by('account_code')
        self.fields['account'].choices = [
            (acc.account_code, f"{acc.account_code} — {acc.account_name}")
            for acc in expense_accounts
        ]

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['invoice', 'amount_paid', 'payment_method', 'payment_date', 'bank_reference']
        widgets = {
            'invoice': forms.Select(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500'}),
            'amount_paid': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500'}),
            'payment_method': forms.Select(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500'}),
            'payment_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500'}),
            'bank_reference': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Invoice
        qs = Invoice.objects.filter(
            payment_status__in=['UNPAID', 'PARTIAL', 'OVERDUE']
        ).select_related('customer', 'shipment').order_by('-created_at')
        self.fields['invoice'].queryset = qs
        self.fields['invoice'].label_from_instance = (
            lambda inv: f"{inv.invoice_number} — {inv.customer.name} — {inv.shipment.awb_number}"
        )

    def clean_amount_paid(self):
        amount = self.cleaned_data.get('amount_paid')
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")
        return amount

    def clean(self):
        cleaned_data = super().clean()
        invoice     = cleaned_data.get('invoice')
        amount_paid = cleaned_data.get('amount_paid')
        if invoice:
            if invoice.payment_status == 'CANCELLED':
                raise forms.ValidationError(
                    f"Invoice {invoice.invoice_number} is cancelled and cannot accept payments."
                )
            if amount_paid:
                already_paid = sum(p.amount_paid for p in invoice.payments.all())
                outstanding  = invoice.total_amount - already_paid
                if outstanding <= 0:
                    raise forms.ValidationError(
                        f"Invoice {invoice.invoice_number} is already fully paid."
                    )
                if amount_paid > outstanding:
                    raise forms.ValidationError(
                        f"Amount exceeds outstanding balance. "
                        f"Maximum payable: Rp {outstanding:,.0f}"
                    )
        return cleaned_data


class InvoiceForm(forms.Form):
    INPUT_CLASS = 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500'

    shipment = forms.ModelChoiceField(
        queryset=None,
        empty_label='— Select a shipment —',
        widget=forms.Select(attrs={
            'class': INPUT_CLASS,
            'x-model': 'selectedId',
            '@change': 'updatePreview()',
        }),
    )
    due_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': INPUT_CLASS}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from shipments.models import Shipment
        eligible = (
            Shipment.objects
            .exclude(status='PENDING')
            .exclude(status='RETURNED')
            .filter(invoice__isnull=True)
            .select_related('customer')
            .order_by('-created_at')
        )
        self.fields['shipment'].queryset = eligible
        self.fields['shipment'].label_from_instance = (
            lambda s: f"{s.awb_number} — {s.customer.name} — {s.get_status_display()}"
        )
