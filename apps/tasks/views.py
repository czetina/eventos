import json
from datetime import date, datetime, time as dt_time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.events.models import (
    Event, EventSectionType, EventSession, IMPORTER_SECTION_CODE_TO_NAME, create_default_section_types,
)
from apps.events.views import get_event_or_403
from apps.vendors.models import Vendor

from . import importers
from .forms import (
    TaskEvidenceForm, TaskForm, TaskImportForm, TaskStatusChangeForm, TaskStatusHistoryEditForm,
)
from .models import Task, TaskEvidence, TaskStatusHistory


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
    tasks = event.tasks.select_related("assigned_to", "supervisor", "itinerary_session")
    if not request.user.can_manage_events:
        tasks = tasks.filter(assigned_to=request.user)
    status = request.GET.get("status")
    if status:
        tasks = tasks.filter(status=status)
    show_overdue = request.GET.get("atrasadas") == "1"
    tasks = list(tasks)
    if show_overdue:
        tasks = [t for t in tasks if t.is_overdue]
    for task in tasks:
        task.latest_status_entry = task.status_history.select_related("changed_by").first()
    return render(request, "tasks/task_list.html", {
        "event": event, "tasks": tasks, "status_choices": Task.STATUS_CHOICES,
        "active_status": status, "show_overdue": show_overdue,
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
            task.record_status_change(request.user)
            messages.success(request, _("Tarea creada y asignada."))
            return redirect("tasks:list", event_pk=event.pk)
    else:
        form = TaskForm(event=event)
    return render(request, "tasks/task_form.html", {"form": form, "event": event, "is_new": True})


@login_required
def task_edit(request, pk):
    task, event = _get_task_scoped(request.user, pk)
    if not (request.user.can_manage_events or request.user.is_supervisor):
        raise PermissionDenied(_("No tienes permiso para editar esta tarea."))
    if request.method == "POST":
        form = TaskForm(request.POST, instance=task, event=event)
        if form.is_valid():
            previous_status = task.status
            task = form.save()
            if task.status != previous_status:
                task.record_status_change(request.user)
            messages.success(request, _("Tarea actualizada."))
            return redirect("tasks:detail", pk=task.pk)
    else:
        form = TaskForm(instance=task, event=event)
    return render(request, "tasks/task_form.html", {"form": form, "event": event, "is_new": False, "task": task})


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
        "status_history": task.status_history.select_related("changed_by"),
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


def _parse_completed_at(request):
    raw = request.POST.get("completed_at", "").strip()
    if not raw:
        return None, False
    try:
        return timezone.make_aware(datetime.strptime(raw, "%Y-%m-%dT%H:%M")), False
    except ValueError:
        return None, True


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

    completed_at, invalid = _parse_completed_at(request)
    if invalid:
        messages.error(request, _("La fecha/hora de finalización no es válida; se usó el momento actual."))

    task.mark_completed(request.user, completed_at=completed_at)
    messages.success(request, _("Tarea marcada como completada el %(time)s.") % {
        "time": timezone.localtime(task.completed_at).strftime("%d/%m/%Y %H:%M")
    })
    return redirect("tasks:detail", pk=task.pk)


@login_required
def task_change_status(request, pk):
    task, event = _get_task_scoped(request.user, pk)
    if not (request.user.can_manage_events or request.user.is_supervisor or task.can_be_completed_by(request.user)):
        raise PermissionDenied(_("No tienes permiso para cambiar el estado de esta tarea."))
    if request.method == "POST":
        form = TaskStatusChangeForm(request.POST)
        if form.is_valid():
            status = form.cleaned_data["status"]
            if status == Task.STATUS_DONE and task.requires_evidence and not task.evidences.exists():
                messages.error(request, _("Esta tarea requiere subir evidencia (foto/documento) antes de completarla."))
            else:
                changed_at = timezone.make_aware(form.cleaned_data["changed_at"]) \
                    if timezone.is_naive(form.cleaned_data["changed_at"]) else form.cleaned_data["changed_at"]
                task.change_status(request.user, status, changed_at=changed_at, note=form.cleaned_data["note"])
                messages.success(request, _("Estado actualizado a %(status)s.") % {"status": task.get_status_display()})
                return redirect("tasks:detail", pk=task.pk)
    else:
        form = TaskStatusChangeForm(initial={"status": task.status, "changed_at": timezone.localtime(timezone.now())})
    return render(request, "tasks/task_status_change_form.html", {"form": form, "task": task, "event": event})


@login_required
def task_status_history_edit(request, pk, history_pk):
    task, event = _get_task_scoped(request.user, pk)
    if not (request.user.can_manage_events or request.user.is_supervisor):
        raise PermissionDenied(_("No tienes permiso para editar el historial de estado."))
    entry = get_object_or_404(TaskStatusHistory, pk=history_pk, task=task)
    if request.method == "POST":
        form = TaskStatusHistoryEditForm(request.POST, instance=entry)
        if form.is_valid():
            entry = form.save(commit=False)
            if timezone.is_naive(entry.changed_at):
                entry.changed_at = timezone.make_aware(entry.changed_at)
            entry.save()
            task.recompute_status_from_history()
            messages.success(request, _("Entrada del historial actualizada."))
            return redirect("tasks:detail", pk=task.pk)
    else:
        form = TaskStatusHistoryEditForm(instance=entry)
    return render(request, "tasks/task_status_history_edit_form.html", {"form": form, "task": task, "event": event})


@login_required
def task_status_history_delete(request, pk, history_pk):
    task, event = _get_task_scoped(request.user, pk)
    if not (request.user.can_manage_events or request.user.is_supervisor):
        raise PermissionDenied(_("No tienes permiso para eliminar entradas del historial de estado."))
    entry = get_object_or_404(TaskStatusHistory, pk=history_pk, task=task)
    if request.method == "POST":
        entry.delete()
        task.recompute_status_from_history()
        messages.success(request, _("Entrada del historial eliminada."))
    return redirect("tasks:detail", pk=task.pk)


@login_required
def task_bulk_complete(request):
    if request.method != "POST":
        return redirect("tasks:my_tasks")

    next_url = request.POST.get("next") or "tasks:my_tasks"
    task_ids = request.POST.getlist("task_ids")
    if not task_ids:
        messages.error(request, _("No seleccionaste ninguna tarea."))
        return redirect(next_url)

    completed_at, invalid = _parse_completed_at(request)
    if invalid:
        messages.error(request, _("La fecha/hora de finalización no es válida; se usó el momento actual."))

    tasks = Task.objects.filter(pk__in=task_ids).select_related("event")
    completed, skipped_permission, skipped_evidence = 0, 0, 0
    for task in tasks:
        try:
            get_event_or_403(request.user, task.event_id)
        except PermissionDenied:
            skipped_permission += 1
            continue
        if not task.can_be_completed_by(request.user):
            skipped_permission += 1
            continue
        if task.requires_evidence and not task.evidences.exists():
            skipped_evidence += 1
            continue
        task.mark_completed(request.user, completed_at=completed_at)
        completed += 1

    if completed:
        messages.success(request, _("%(count)s tareas marcadas como completadas.") % {"count": completed})
    if skipped_evidence:
        messages.warning(request, _(
            "%(count)s tareas se omitieron porque requieren evidencia y todavía no la tienen."
        ) % {"count": skipped_evidence})
    if skipped_permission:
        messages.warning(request, _("%(count)s tareas se omitieron porque no tienes permiso para completarlas.") % {
            "count": skipped_permission
        })
    return redirect(next_url)


TITLE_MAX_LEN = 200
PLANNER_ROLE_ALIASES = {"planner", "planificador", "planner ", "planer"}


def _row_to_payload(row, candidate_users, candidate_vendors, event):
    """Truncates long titles (the full text is kept for the description), folds in
    any location/vendor-category hints from richer formats, and resolves the
    responsible name to an existing user or vendor when possible ('Planner' maps
    straight to the event's assigned planner, since that role is already known)."""
    title = row.title
    extra_description = ""
    if len(title) > TITLE_MAX_LEN:
        title = title[: TITLE_MAX_LEN - 1] + "…"
        extra_description = row.title

    notes = []
    if row.location and importers.normalize_text(row.location) != "escritorio":
        notes.append(f"Ubicación: {row.location}")
    if row.supplier_hint:
        notes.append(f"Proveedor sugerido (por asignar): {row.supplier_hint}")
    if notes:
        extra_description = (extra_description or row.title) + "\n\n" + "\n".join(notes)

    matched_user = None
    if importers.normalize_text(row.responsible_name) in PLANNER_ROLE_ALIASES and event.planner_id:
        matched_user = event.planner
    if not matched_user:
        matched_user = importers.match_user_by_name(row.responsible_name, candidate_users)
    matched_vendor = None if matched_user else importers.match_vendor_by_name(row.responsible_name, candidate_vendors)
    return {
        "title": title,
        "description": extra_description,
        "category": row.category,
        "responsible_name": row.responsible_name,
        "due_date": row.due_date.isoformat() if row.due_date else "",
        "due_time": row.due_time.strftime("%H:%M") if row.due_time else "",
        "done": row.done,
        "matched_user_id": matched_user.id if matched_user else None,
        "matched_user_display": str(matched_user) if matched_user else "",
        "matched_vendor_id": matched_vendor.id if matched_vendor else None,
        "matched_vendor_display": str(matched_vendor.name) if matched_vendor else "",
    }


@login_required
def task_import(request, event_pk):
    event = get_event_or_403(request.user, event_pk)
    if not request.user.can_manage_events:
        raise PermissionDenied(_("Solo planificadores o administradores pueden importar tareas."))

    if request.method == "POST":
        form = TaskImportForm(request.POST, request.FILES)
        if form.is_valid():
            source_type = form.cleaned_data["source_type"]
            uploaded = form.cleaned_data["file"]
            candidate_users = list(User.objects.filter(company=event.company, is_active=True))
            candidate_vendors = list(Vendor.objects.filter(company=event.company))
            try:
                if source_type == TaskImportForm.SOURCE_TASK_PER_PERSON:
                    rows = importers.parse_task_per_person(uploaded)
                elif source_type == TaskImportForm.SOURCE_GUION_FINAL:
                    rows = importers.parse_guion_final(uploaded)
                else:
                    rows = importers.parse_guion_completo(uploaded)
            except ValueError as exc:
                messages.error(request, str(exc))
                return render(request, "tasks/task_import.html", {"form": form, "event": event})

            if not rows:
                messages.error(request, _("No se encontraron filas para importar en ese archivo."))
                return render(request, "tasks/task_import.html", {"form": form, "event": event})

            payload = [_row_to_payload(r, candidate_users, candidate_vendors, event) for r in rows]

            itinerary_payload = []
            section_types = create_default_section_types(event.company)
            if source_type == TaskImportForm.SOURCE_GUION_FINAL:
                proposals = importers.propose_itinerary_from_rows(rows, event.event_date)
                itinerary_payload = [{
                    "due_date": p["due_date"].isoformat(),
                    "start_time": p["start_time"].strftime("%H:%M"),
                    "venue_name": p["venue_name"],
                    "title": p["title"],
                    "notes": p["notes"],
                    "section": section_types[IMPORTER_SECTION_CODE_TO_NAME[p["section"]]].pk,
                    "section_label": section_types[IMPORTER_SECTION_CODE_TO_NAME[p["section"]]].name,
                } for p in proposals]

            return render(request, "tasks/task_import_preview.html", {
                "event": event,
                "rows": payload,
                "payload_json": json.dumps(payload),
                "candidate_users": candidate_users,
                "candidate_vendors": candidate_vendors,
                "itinerary_rows": itinerary_payload,
                "itinerary_payload_json": json.dumps(itinerary_payload),
                "section_choices": [(t.pk, t.name) for t in EventSectionType.objects.filter(company=event.company)],
            })
    else:
        form = TaskImportForm()
    return render(request, "tasks/task_import.html", {"form": form, "event": event})


@login_required
def task_import_confirm(request, event_pk):
    event = get_event_or_403(request.user, event_pk)
    if not request.user.can_manage_events:
        raise PermissionDenied(_("Solo planificadores o administradores pueden importar tareas."))
    if request.method != "POST":
        return redirect("tasks:import", event_pk=event.pk)

    try:
        rows = json.loads(request.POST.get("payload", "[]"))
    except json.JSONDecodeError:
        messages.error(request, _("No se pudo leer la información a importar."))
        return redirect("tasks:import", event_pk=event.pk)

    created = 0
    for index, row in enumerate(rows):
        assigned_to = None
        vendor = None

        # The planner may have changed the proposed assignee in the review screen —
        # that choice wins over whatever the parser auto-matched. "external" means
        # "no system user/vendor" (explicitly chosen or left as auto-matched none).
        override = request.POST.get(f"assignee_{index}", "")
        if override.startswith("user:"):
            assigned_to = User.objects.filter(pk=override.split(":", 1)[1], company=event.company).first()
        elif override.startswith("vendor:"):
            vendor = Vendor.objects.filter(pk=override.split(":", 1)[1], company=event.company).first()
        elif override != "external":
            # Defensive fallback if the field was somehow missing from the submit.
            if row.get("matched_user_id"):
                assigned_to = User.objects.filter(pk=row["matched_user_id"], company=event.company).first()
            elif row.get("matched_vendor_id"):
                vendor = Vendor.objects.filter(pk=row["matched_vendor_id"], company=event.company).first()

        task = Task(
            event=event,
            title=row["title"],
            description=row.get("description", ""),
            category=row.get("category", ""),
            assigned_to=assigned_to,
            vendor=vendor,
            external_assignee_name="" if (assigned_to or vendor) else row.get("responsible_name", ""),
            due_date=date.fromisoformat(row["due_date"]) if row.get("due_date") else None,
            due_time=dt_time.fromisoformat(row["due_time"]) if row.get("due_time") else None,
            created_by=request.user,
        )
        if row.get("done"):
            task.status = Task.STATUS_DONE
            task.completed_at = timezone.now()
            task.completed_by = request.user
        task.save()
        task.record_status_change(request.user, note=_("Importada"))
        created += 1

    itinerary_created = 0
    try:
        itinerary_rows = json.loads(request.POST.get("itinerary_payload", "[]"))
    except json.JSONDecodeError:
        itinerary_rows = []
    if itinerary_rows:
        next_order = (event.sessions.aggregate(Max("order"))["order__max"] or 0) + 1
        default_section = create_default_section_types(event.company)["Otro"]
        for index, row in enumerate(itinerary_rows):
            if request.POST.get(f"itinerary_include_{index}") != "on":
                continue
            time_value = request.POST.get(f"itinerary_time_{index}", row.get("start_time", ""))
            date_value = request.POST.get(f"itinerary_date_{index}", row.get("due_date", ""))
            section_id = request.POST.get(f"itinerary_section_{index}", row.get("section", ""))
            section = EventSectionType.objects.filter(pk=section_id, company=event.company).first() or default_section
            try:
                start_time = dt_time.fromisoformat(time_value)
                session_date = date.fromisoformat(date_value)
            except ValueError:
                continue
            EventSession.objects.create(
                event=event,
                section=section,
                title=row["title"],
                venue_name=row.get("venue_name", ""),
                date=session_date,
                start_time=start_time,
                notes=row.get("notes", ""),
                order=next_order,
            )
            next_order += 1
            itinerary_created += 1

    if itinerary_created:
        messages.success(request, _("Se importaron %(count)s tareas y %(sessions)s actividades de itinerario.") % {
            "count": created, "sessions": itinerary_created
        })
    else:
        messages.success(request, _("Se importaron %(count)s tareas correctamente.") % {"count": created})
    return redirect("tasks:list", event_pk=event.pk)
