import json
from datetime import date, datetime, time as dt_time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
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
    TaskChainForm, TaskEvidenceForm, TaskForm, TaskImportForm, TaskStatusChangeForm, TaskStatusHistoryEditForm,
)
from .models import Task, TaskChain, TaskEvidence, TaskStatusHistory


def _annotate_chain_step(tasks):
    """Attaches .chain_step/.chain_total (this task's position within its chain,
    if any) to each task in a single extra query, regardless of how many
    distinct chains are involved — avoids a per-task query in list templates."""
    tasks = list(tasks)
    chain_ids = {t.chain_id for t in tasks if t.chain_id}
    ids_by_chain = {}
    if chain_ids:
        for row in Task.objects.filter(chain_id__in=chain_ids).order_by("chain_order").values("id", "chain_id"):
            ids_by_chain.setdefault(row["chain_id"], []).append(row["id"])
    for t in tasks:
        chain_task_ids = ids_by_chain.get(t.chain_id, []) if t.chain_id else []
        t.chain_total = len(chain_task_ids)
        t.chain_step = chain_task_ids.index(t.id) + 1 if t.id in chain_task_ids else None
    return tasks


@login_required
def my_tasks(request):
    """Mobile-friendly checklist: everything assigned to the logged-in user, across events."""
    tasks = _annotate_chain_step(
        Task.objects.filter(assigned_to=request.user)
        .exclude(status=Task.STATUS_DONE)
        .select_related("event", "chain")
        .order_by("due_date", "due_time")
    )
    done_tasks = _annotate_chain_step(
        Task.objects.filter(assigned_to=request.user, status=Task.STATUS_DONE)
        .select_related("event", "chain")
        .order_by("-completed_at")[:20]
    )
    return render(request, "tasks/my_tasks.html", {"tasks": tasks, "done_tasks": done_tasks})


@login_required
def task_list(request, event_pk):
    event = get_event_or_403(request.user, event_pk)
    tasks = event.tasks.select_related("assigned_to", "supervisor", "itinerary_session", "chain")
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
    ics_public_url = request.build_absolute_uri(
        reverse("tasks:export_guion_ics_public", args=[event.share_token])
    )
    subscribe_url = ics_public_url.replace("http://", "webcal://").replace("https://", "webcal://")
    return render(request, "tasks/task_list.html", {
        "event": event, "tasks": tasks, "status_choices": Task.STATUS_CHOICES,
        "active_status": status, "show_overdue": show_overdue,
        "guion_subscribe_url": subscribe_url, "guion_subscribe_url_https": ics_public_url,
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


@login_required
def task_delete(request, pk):
    task, event = _get_task_scoped(request.user, pk)
    if not (request.user.can_manage_events or request.user.is_supervisor):
        raise PermissionDenied(_("No tienes permiso para eliminar esta tarea."))
    if request.method == "POST":
        for evidence in task.evidences.all():
            evidence.file.delete(save=False)
        task.delete()
        messages.success(request, _("Tarea eliminada."))
        return redirect("tasks:list", event_pk=event.pk)
    return redirect("tasks:detail", pk=task.pk)


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
    chain_step, chain_total = None, None
    if task.chain_id:
        chain_task_ids = list(task.chain.tasks.order_by("chain_order").values_list("id", flat=True))
        chain_total = len(chain_task_ids)
        if task.id in chain_task_ids:
            chain_step = chain_task_ids.index(task.id) + 1
    return render(request, "tasks/task_detail.html", {
        "task": task, "event": event,
        "evidences": task.evidences.select_related("uploaded_by"),
        "evidence_form": evidence_form,
        "can_complete": task.can_be_completed_by(request.user),
        "status_history": task.status_history.select_related("changed_by"),
        "chain_step": chain_step, "chain_total": chain_total,
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
def task_delete_evidence(request, pk, evidence_pk):
    task, event = _get_task_scoped(request.user, pk)
    evidence = get_object_or_404(TaskEvidence, pk=evidence_pk, task=task)
    if request.method == "POST":
        evidence.file.delete(save=False)
        evidence.delete()
        messages.success(request, _("Evidencia eliminada."))
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


def _get_chain_scoped(user, pk):
    chain = get_object_or_404(TaskChain, pk=pk)
    event = get_event_or_403(user, chain.event_id)
    return chain, event


def _can_manage_chains(user):
    return user.can_manage_events or user.is_supervisor


@login_required
def task_chain_list(request, event_pk):
    event = get_event_or_403(request.user, event_pk)
    chains = event.task_chains.prefetch_related("tasks")
    return render(request, "tasks/task_chain_list.html", {
        "event": event, "chains": chains, "can_manage_chains": _can_manage_chains(request.user),
    })


@login_required
def task_chain_create(request, event_pk):
    event = get_event_or_403(request.user, event_pk)
    if not _can_manage_chains(request.user):
        raise PermissionDenied(_("No tienes permiso para crear cadenas de tareas en este evento."))
    if request.method == "POST":
        form = TaskChainForm(request.POST)
        if form.is_valid():
            chain = form.save(commit=False)
            chain.event = event
            chain.created_by = request.user
            chain.save()
            messages.success(request, _("Cadena de tareas creada."))
            return redirect("tasks:chain_detail", pk=chain.pk)
    else:
        form = TaskChainForm()
    return render(request, "tasks/task_chain_form.html", {"form": form, "event": event, "is_new": True})


@login_required
def task_chain_detail(request, pk):
    chain, event = _get_chain_scoped(request.user, pk)
    tasks = list(chain.tasks.select_related("assigned_to", "supervisor", "vendor").order_by("chain_order"))
    for task in tasks:
        task.latest_status_entry = task.status_history.select_related("changed_by").first()
    available_tasks = event.tasks.filter(chain__isnull=True).order_by("title")
    return render(request, "tasks/task_chain_detail.html", {
        "event": event, "chain": chain, "tasks": tasks, "available_tasks": available_tasks,
        "can_manage_chains": _can_manage_chains(request.user),
    })


@login_required
def task_chain_edit(request, pk):
    chain, event = _get_chain_scoped(request.user, pk)
    if not _can_manage_chains(request.user):
        raise PermissionDenied(_("No tienes permiso para editar esta cadena de tareas."))
    if request.method == "POST":
        form = TaskChainForm(request.POST, instance=chain)
        if form.is_valid():
            form.save()
            messages.success(request, _("Cadena de tareas actualizada."))
            return redirect("tasks:chain_detail", pk=chain.pk)
    else:
        form = TaskChainForm(instance=chain)
    return render(request, "tasks/task_chain_form.html", {
        "form": form, "event": event, "is_new": False, "chain": chain,
    })


@login_required
def task_chain_delete(request, pk):
    chain, event = _get_chain_scoped(request.user, pk)
    if not _can_manage_chains(request.user):
        raise PermissionDenied(_("No tienes permiso para eliminar esta cadena de tareas."))
    if request.method == "POST":
        with transaction.atomic():
            chain.tasks.update(chain=None, chain_order=None)
            chain.delete()
        messages.success(request, _("Cadena de tareas eliminada. Las tareas no se borraron."))
        return redirect("tasks:chain_list", event_pk=event.pk)
    return redirect("tasks:chain_detail", pk=chain.pk)


@login_required
def task_chain_add_task(request, pk):
    chain, event = _get_chain_scoped(request.user, pk)
    if not _can_manage_chains(request.user):
        raise PermissionDenied(_("No tienes permiso para modificar esta cadena de tareas."))
    if request.method == "POST":
        task = get_object_or_404(Task, pk=request.POST.get("task_id"), event=event, chain__isnull=True)
        next_order = (chain.tasks.aggregate(Max("chain_order"))["chain_order__max"] or 0) + 1
        task.chain = chain
        task.chain_order = next_order
        task.save(update_fields=["chain", "chain_order"])
        messages.success(request, _("Tarea agregada a la cadena."))
    return redirect("tasks:chain_detail", pk=chain.pk)


@login_required
def task_chain_create_task(request, pk):
    chain, event = _get_chain_scoped(request.user, pk)
    if not _can_manage_chains(request.user):
        raise PermissionDenied(_("No tienes permiso para crear tareas en esta cadena."))
    if request.method == "POST":
        form = TaskForm(request.POST, event=event)
        if form.is_valid():
            next_order = (chain.tasks.aggregate(Max("chain_order"))["chain_order__max"] or 0) + 1
            task = form.save(commit=False)
            task.event = event
            task.created_by = request.user
            task.chain = chain
            task.chain_order = next_order
            task.save()
            task.record_status_change(request.user)
            messages.success(request, _("Tarea creada y agregada a la cadena."))
            return redirect("tasks:chain_detail", pk=chain.pk)
    else:
        form = TaskForm(event=event)
    return render(request, "tasks/task_form.html", {
        "form": form, "event": event, "is_new": True, "chain": chain,
    })


@login_required
def task_chain_remove_task(request, pk, task_pk):
    chain, event = _get_chain_scoped(request.user, pk)
    if not _can_manage_chains(request.user):
        raise PermissionDenied(_("No tienes permiso para modificar esta cadena de tareas."))
    task = get_object_or_404(Task, pk=task_pk, chain=chain)
    if request.method == "POST":
        task.chain = None
        task.chain_order = None
        task.save(update_fields=["chain", "chain_order"])
        messages.success(request, _("Tarea quitada de la cadena. La tarea no se eliminó."))
    return redirect("tasks:chain_detail", pk=chain.pk)


@login_required
def task_chain_move(request, pk, task_pk, direction):
    chain, event = _get_chain_scoped(request.user, pk)
    if not _can_manage_chains(request.user):
        raise PermissionDenied(_("No tienes permiso para modificar esta cadena de tareas."))
    task = get_object_or_404(Task, pk=task_pk, chain=chain)
    if request.method == "POST":
        ordered = list(chain.tasks.order_by("chain_order"))
        index = next((i for i, t in enumerate(ordered) if t.pk == task.pk), None)
        if index is not None:
            neighbor_index = index - 1 if direction == "up" else index + 1
            if 0 <= neighbor_index < len(ordered):
                neighbor = ordered[neighbor_index]
                task_order, neighbor_order = task.chain_order, neighbor.chain_order
                with transaction.atomic():
                    # Swap via a temporary NULL first — the (chain, chain_order)
                    # constraint only applies to non-null orders, so this avoids
                    # a momentary collision when both rows would otherwise share
                    # the same order value between the two save() calls.
                    task.chain_order = None
                    task.save(update_fields=["chain_order"])
                    neighbor.chain_order = task_order
                    neighbor.save(update_fields=["chain_order"])
                    task.chain_order = neighbor_order
                    task.save(update_fields=["chain_order"])
    return redirect("tasks:chain_detail", pk=chain.pk)


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
                "replace_existing": form.cleaned_data["replace_existing"],
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

    replaced = 0
    if request.POST.get("replace_existing") == "1":
        replaced = event.tasks.count()
        event.tasks.all().delete()

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
    if replaced:
        messages.info(request, _("Se borraron %(count)s tareas existentes antes de importar.") % {"count": replaced})
    return redirect("tasks:list", event_pk=event.pk)


def _build_guion_calendar(event):
    """Builds the icalendar Calendar with every 'guión' task that has a due
    date/time, each with a 15-minute reminder alarm. Shared by the logged-in
    download and the public webcal subscription feed, so both always produce
    the exact same events."""
    from icalendar import Alarm, Calendar
    from icalendar import Event as ICalEvent

    tasks = event.tasks.filter(
        is_guion=True, due_date__isnull=False, due_time__isnull=False,
    ).select_related("assigned_to", "vendor").order_by("due_date", "due_time")

    cal = Calendar()
    cal.add("prodid", f"-//EventPlanner//{event.pk}//ES")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", f"{_('Guión')} — {event.name}")

    for task in tasks:
        start = datetime.combine(task.due_date, task.due_time)
        ical_event = ICalEvent()
        ical_event.add("uid", f"eventplanner-task-{task.pk}@eventplanner")
        ical_event.add("summary", task.title)
        ical_event.add("dtstart", start)
        ical_event.add("dtend", start + timedelta(minutes=15))
        ical_event.add("dtstamp", timezone.now())
        description = _("Responsable: %(name)s") % {"name": task.responsible_display}
        if task.description:
            description = f"{task.description}\n\n{description}"
        ical_event.add("description", description)
        if event.venue_name:
            ical_event.add("location", event.venue_name)

        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", task.title)
        alarm.add("trigger", timedelta(minutes=-15))
        ical_event.add_component(alarm)

        cal.add_component(ical_event)

    return cal


@login_required
def task_export_guion_ics(request, event_pk):
    """Downloads a one-time snapshot .ics of the 'guión' tasks — good for
    emailing to yourself or opening directly in Mail's Add-to-Calendar flow."""
    event = get_event_or_403(request.user, event_pk)
    cal = _build_guion_calendar(event)
    response = HttpResponse(cal.to_ical(), content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="guion_{event.pk}.ics"'
    return response


def task_export_guion_ics_public(request, token):
    """No-login webcal feed keyed by the event's existing public share_token
    (same token already used for the processional-diagram public link) —
    subscribing to this URL (webcal://...) makes the phone's Calendar app
    create its own separate, auto-refreshing calendar for the event, instead
    of dumping the events into whatever calendar is currently selected."""
    event = get_object_or_404(Event, share_token=token)
    cal = _build_guion_calendar(event)
    return HttpResponse(cal.to_ical(), content_type="text/calendar; charset=utf-8")
