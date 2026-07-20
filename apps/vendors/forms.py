from django import forms
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.forms import BootstrapFormMixin

from .models import EventVendor, Vendor, VendorCategory, VendorPayment


class VendorCategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = VendorCategory
        fields = ["name", "order"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class VendorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ["name", "category", "contact_name", "phone", "email", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields["category"].queryset = VendorCategory.objects.filter(company=company)
        self._apply_bootstrap()


class VendorDeactivateForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ["deactivated_on"]
        widgets = {"deactivated_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["deactivated_on"].required = True
        self.fields["deactivated_on"].label = _("fecha de baja")
        self._apply_bootstrap()


class EventVendorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = EventVendor
        fields = ["vendor", "contract_amount", "status", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, company=None, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            active_filter = models.Q(is_active=True)
            if self.instance.pk:
                # Keep an already-deactivated vendor selectable on this existing booking
                # so editing it doesn't force picking a new vendor.
                active_filter |= models.Q(pk=self.instance.vendor_id)
            self.fields["vendor"].queryset = Vendor.objects.filter(active_filter, company=company)
        if event:
            already = EventVendor.objects.filter(event=event)
            if self.instance.pk:
                already = already.exclude(pk=self.instance.pk)
            self.fields["vendor"].queryset = self.fields["vendor"].queryset.exclude(
                pk__in=already.values_list("vendor_id", flat=True)
            )
        self._apply_bootstrap()


class VendorPaymentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = VendorPayment
        fields = ["date", "amount", "document", "note"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].input_formats = ["%Y-%m-%d"]
        self.fields["document"].required = False
        self.fields["note"].required = False
        self._apply_bootstrap()
