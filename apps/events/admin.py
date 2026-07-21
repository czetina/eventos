from django.contrib import admin

from .models import (
    Event, EventAdvance, EventSectionType, EventSession, EventTeamMember, Expense, Invoice,
    InvoiceItem, MealCount, ProcessionalEntry, Quotation, QuotationItem, SeatingTable, TableGuest,
    WeddingPartyMember, WeddingPartyListType, WeddingTableType,
)


class EventSessionInline(admin.TabularInline):
    model = EventSession
    extra = 0


class EventTeamMemberInline(admin.TabularInline):
    model = EventTeamMember
    extra = 0
    fk_name = "event"


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["name", "company", "event_type", "country", "city", "event_date", "status"]
    list_filter = ["status", "event_type", "country", "company"]
    search_fields = ["name", "client_name", "city"]
    date_hierarchy = "event_date"
    inlines = [EventSessionInline, EventTeamMemberInline]


@admin.register(EventSectionType)
class EventSectionTypeAdmin(admin.ModelAdmin):
    list_display = ["company", "name", "order"]
    list_filter = ["company"]


@admin.register(EventTeamMember)
class EventTeamMemberAdmin(admin.ModelAdmin):
    list_display = ["event", "user", "role", "area", "reports_to"]
    list_filter = ["role"]


@admin.register(WeddingPartyListType)
class WeddingPartyListTypeAdmin(admin.ModelAdmin):
    list_display = ["company", "name", "order"]
    list_filter = ["company"]


@admin.register(WeddingPartyMember)
class WeddingPartyMemberAdmin(admin.ModelAdmin):
    list_display = ["event", "list_type", "name", "role_description", "quantity", "order", "table_number"]
    list_filter = ["list_type"]
    search_fields = ["name"]


@admin.register(ProcessionalEntry)
class ProcessionalEntryAdmin(admin.ModelAdmin):
    list_display = ["event", "phase", "order", "left_name", "center_name", "right_name", "music"]
    list_filter = ["event", "phase"]


@admin.register(MealCount)
class MealCountAdmin(admin.ModelAdmin):
    list_display = ["event", "group", "meal_label", "count"]
    list_filter = ["group"]


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ["event", "date", "description", "amount", "created_by"]
    list_filter = ["event"]
    date_hierarchy = "date"


@admin.register(EventAdvance)
class EventAdvanceAdmin(admin.ModelAdmin):
    list_display = ["event", "date", "amount", "created_by"]
    list_filter = ["event"]
    date_hierarchy = "date"


@admin.register(WeddingTableType)
class WeddingTableTypeAdmin(admin.ModelAdmin):
    list_display = ["company", "name", "order"]
    list_filter = ["company"]


class TableGuestInline(admin.TabularInline):
    model = TableGuest
    extra = 0


@admin.register(SeatingTable)
class SeatingTableAdmin(admin.ModelAdmin):
    list_display = ["event", "table_number", "table_type", "capacity"]
    list_filter = ["event", "table_type"]
    inlines = [TableGuestInline]


class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 0


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ["event", "activity", "client_name", "realization_date", "exchange_rate"]
    list_filter = ["event"]
    inlines = [QuotationItemInline]


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["event", "invoice_number", "date", "bill_to_name"]
    list_filter = ["event"]
    inlines = [InvoiceItemInline]
