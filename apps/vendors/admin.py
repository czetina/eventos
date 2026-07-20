from django.contrib import admin

from .models import EventVendor, Vendor, VendorCategory, VendorPayment


@admin.register(VendorCategory)
class VendorCategoryAdmin(admin.ModelAdmin):
    list_display = ["company", "name", "order"]
    list_filter = ["company"]


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ["name", "company", "category", "contact_name", "phone", "is_active"]
    list_filter = ["category", "company", "is_active"]
    search_fields = ["name", "contact_name"]


class VendorPaymentInline(admin.TabularInline):
    model = VendorPayment
    extra = 0


@admin.register(EventVendor)
class EventVendorAdmin(admin.ModelAdmin):
    list_display = ["event", "vendor", "contract_amount", "deposit_paid", "status"]
    list_filter = ["status"]
    inlines = [VendorPaymentInline]
