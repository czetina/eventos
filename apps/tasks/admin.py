from django.contrib import admin

from .models import Task, TaskChain, TaskEvidence, TaskStatusHistory


class TaskEvidenceInline(admin.TabularInline):
    model = TaskEvidence
    extra = 0


class TaskStatusHistoryInline(admin.TabularInline):
    model = TaskStatusHistory
    extra = 0
    readonly_fields = ["status", "changed_at", "changed_by", "note"]
    can_delete = False


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = [
        "title", "event", "assigned_to", "vendor", "supervisor", "status", "due_date", "due_time", "chain",
    ]
    list_filter = ["status", "requires_photo", "requires_document"]
    search_fields = ["title", "event__name"]
    inlines = [TaskEvidenceInline, TaskStatusHistoryInline]


@admin.register(TaskChain)
class TaskChainAdmin(admin.ModelAdmin):
    list_display = ["name", "event", "created_by", "created_at"]
    search_fields = ["name", "event__name"]
