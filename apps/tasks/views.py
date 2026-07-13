from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from apps.events.models import Event
from apps.events.views import get_event_or_403

from .forms import TaskEvidenceForm, TaskForm
from .models import Task, TaskEvidence


@login_required
def my_tasks(request):
    """Mobile-friendly checklist: everything assigned to the logged-in user, across events."""
    tasks = (
        Task.objects.filter(assigned_to=request.user)
        .exclude(status=Task.STATUS_DONE)
        .select_related("event")
        .order_by("due_date", "due_time")
    )
    done_tasks = (
        Task.objects.filter(assigned_to=request.user, status=Task.STATUS_DONE)
        .select_related("event")
        .order_by("-completed_at")[:20]
    )
    return render(request, "tasks/my_tasks.html", {"tasks": tasks, "done_tasks": done_tasks})


@login_required
def task_list(request, event_pk):
    event = get_event_or_403(request.user, event_pk)
    tasks = event.tasks.select_related("assigned_to", "supervisor")
    if not request.user.can_manage_events:
        tasks = tasks.filter(assigned_to=request.user)
    status = request.GET.get("status")
    if status:
        tasks = tasks.filter(status=status)
    return render(request, "tasks/task_list.html", {
        "event": event, "tasks": tasks, "status_choices": Task.STATUS_CHOICES, "active_status": status,
    })


@login_required
def task_create(request, event_pk):
    event = get_event_or_403(request.user, event_pk)
    if not (request.user.can_manage_events or request.user.is_supervisor):
        raise PermissionDenied(_("No tienes permiso para crear tareas en este evento."))
    if request.method == "POST":
        form = TaskForm(request.POST, event=event)
        if form.is_valid():
            task = form.save(commit=False)
            task.event = event
            task.created_by = request.user
            task.save()
            messages.success(request, _("Tarea creada y asignada."))
            return redirect("tasks:list", event_pk=event.pk)
    else:
        form = TaskForm(event=event)
    return render(request, "tasks/task_form.html", {"form": form, "event": event})


def _get_task_scoped(user, pk):
    task = get_object_or_404(Task, pk=pk)
    event = get_event_or_403(user, task.event_id)
    if not user.can_manage_events and task.assigned_to_id != user.id and task.supervisor_id != user.id:
        raise PermissionDenied(_("No tienes acceso a esta tarea."))
    return task, event


@login_required
def task_detail(request, pk):
    task, event = _get_task_scoped(request.user, pk)
    evidence_form = TaskEvidenceForm()
    return render(request, "tasks/task_detail.html", {
        "task": task, "event": event,
        "evidences": task.evidences.select_related("uploaded_by"),
        "evidence_form": evidence_form,
        "can_complete": task.can_be_completed_by(request.user),
    })


@login_required
def task_upload_evidence(request, pk):
    task, event = _get_task_scoped(request.user, pk)
    if request.method == "POST":
        form = TaskEvidenceForm(request.POST, request.FILES)
        if form.is_valid():
            evidence = form.save(commit=False)
            evidence.task = task
            evidence.uploaded_by = request.user
            evidence.save()
            messages.success(request, _("Evidencia subida correctamente."))
        else:
            messages.error(request, _("No se pudo subir la evidencia. Revisa el archivo."))
    return redirect("tasks:detail", pk=task.pk)


@login_required
def task_complete(request, pk):
    task, event = _get_task_scoped(request.user, pk)
    if request.method != "POST":
        return redirect("tasks:detail", pk=task.pk)
    if not task.can_be_completed_by(request.user):
        raise PermissionDenied(_("Solo el encargado o un supervisor pueden completar esta tarea."))
    if task.requires_evidence and not task.evidences.exists():
        messages.error(request, _("Esta tarea requiere subir evidencia (foto/documento) antes de completarla."))
        return redirect("tasks:detail", pk=task.pk)
    task.mark_completed(request.user)
    messages.success(request, _("Tarea marcada como completada a las %(time)s.") % {
        "time": task.completed_at.strftime("%H:%M")
    })
    return redirect("tasks:detail", pk=task.pk)
