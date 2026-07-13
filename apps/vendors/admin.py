from django.contrib import admin

from .models import EventVendor, Vendor


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ["name", "company", "category", "contact_name", "phone"]
    list_filter = ["category", "company"]
    search_fields = ["name", "contact_name"]


@admin.register(EventVendor)
class EventVendorAdmin(admin.ModelAdmin):
    list_display = ["event", "vendor", "contract_amount", "deposit_paid", "status"]
    list_filter = ["status"]
