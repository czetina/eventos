from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Company, User


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name", "country", "city", "is_active", "created_at"]
    list_filter = ["is_active", "country"]
    search_fields = ["name", "city"]


@admin.register(User)
class CompanyUserAdmin(UserAdmin):
    list_display = ["username", "email", "first_name", "last_name", "company", "role", "is_active"]
    list_filter = ["role", "company", "is_active"]
    fieldsets = UserAdmin.fieldsets + (
        ("Empresa y rol", {"fields": ("company", "role", "phone", "preferred_language")}),
    )
