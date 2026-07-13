from django.contrib import admin

from .models import Event, EventSession, EventTeamMember


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


@admin.register(EventTeamMember)
class EventTeamMemberAdmin(admin.ModelAdmin):
    list_display = ["event", "user", "role_in_event", "area", "reports_to"]
    list_filter = ["role_in_event"]
