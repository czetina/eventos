from django.contrib import admin

from .models import EventFile, Note


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ["event", "author", "pinned", "created_at"]
    list_filter = ["pinned"]


@admin.register(EventFile)
class EventFileAdmin(admin.ModelAdmin):
    list_display = ["event", "title", "uploaded_by", "uploaded_at"]
