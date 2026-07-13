from django import forms

from apps.accounts.forms import BootstrapFormMixin

from .models import EventVendor, Vendor


class VendorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ["name", "category", "contact_name", "phone", "email", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class EventVendorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = EventVendor
        fields = ["vendor", "contract_amount", "deposit_paid", "status", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, company=None, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields["vendor"].queryset = Vendor.objects.filter(company=company)
        if event:
            already = EventVendor.objects.filter(event=event).values_list("vendor_id", flat=True)
            self.fields["vendor"].queryset = self.fields["vendor"].queryset.exclude(pk__in=already)
        self._apply_bootstrap()
