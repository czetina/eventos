from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.events.views import get_event_or_403

from .forms import EventFileForm, NoteForm
from .models import EventFile, Note


@login_required
def note_list(request, event_pk):
    event = get_event_or_403(request.user, event_pk)
    if request.method == "POST":
        form = NoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.event = event
            note.author = request.user
            note.save()
            messages.success(request, "Nota agregada.")
            return redirect("notes:list", event_pk=event.pk)
    else:
        form = NoteForm()
    return render(request, "notes/note_list.html", {"event": event, "notes": event.notes.all(), "form": form})


@login_required
def note_delete(request, event_pk, pk):
    event = get_event_or_403(request.user, event_pk)
    note = get_object_or_404(Note, pk=pk, event=event)
    if request.method == "POST" and (request.user == note.author or request.user.can_manage_events):
        note.delete()
        messages.success(request, "Nota eliminada.")
    return redirect("notes:list", event_pk=event.pk)


@login_required
def file_list(request, event_pk):
    event = get_event_or_403(request.user, event_pk)
    if request.method == "POST":
        form = EventFileForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.save(commit=False)
            f.event = event
            f.uploaded_by = request.user
            f.save()
            messages.success(request, "Archivo subido.")
            return redirect("notes:files", event_pk=event.pk)
    else:
        form = EventFileForm()
    return render(request, "notes/file_list.html", {"event": event, "files": event.files.all(), "form": form})


@login_required
def file_delete(request, event_pk, pk):
    event = get_event_or_403(request.user, event_pk)
    if not request.user.can_manage_events:
        return redirect("notes:files", event_pk=event.pk)
    ef = get_object_or_404(EventFile, pk=pk, event=event)
    if request.method == "POST":
        ef.delete()
        messages.success(request, "Archivo eliminado.")
    return redirect("notes:files", event_pk=event.pk)
