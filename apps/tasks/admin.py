from django.contrib import admin

from .models import Task, TaskEvidence


class TaskEvidenceInline(admin.TabularInline):
    model = TaskEvidence
    extra = 0


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "event", "assigned_to", "supervisor", "status", "due_date", "due_time"]
    list_filter = ["status", "requires_photo", "requires_document"]
    search_fields = ["title", "event__name"]
    inlines = [TaskEvidenceInline]
