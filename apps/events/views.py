import json
from datetime import time as dt_time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Max, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from django.utils.translation import gettext_lazy as _

from apps.notes.forms import NoteForm

from . import importers
from .forms import (
    EventForm, EventSessionForm, EventTeamMemberForm, MealCountForm,
    ProcessionalEntryForm, SessionImportForm, WeddingPartyMemberForm, WeddingPartyListTypeForm,
)
from .models import (
    Event, EventSession, EventTeamMember, MealCount, ProcessionalEntry, WeddingPartyMember,
    WeddingPartyListType, create_default_wedding_party_list_types,
)


def events_visible_to(user):
    """Scope events by tenant + role: admins/planners see the whole company,
    supervisors/encargados only see events where they are on the team."""
    if not user.company:
        return Event.objects.none()
    qs = Event.objects.filter(company=user.company)
    if user.can_manage_events:
        return qs
    return qs.filter(team_members__user=user).distinct()


def get_event_or_403(user, pk):
    event = get_object_or_404(Event, pk=pk)
    if event.company_id != user.company_id:
        raise PermissionDenied
    if not user.can_manage_events and not event.team_members.filter(user=user).exists():
        raise PermissionDenied(_("No perteneces al equipo de este evento."))
    return event


@login_required
def event_list(request):
    events = events_visible_to(request.user).order_by("-event_date")
    return render(request, "events/event_list.html", {"events": events})


@login_required
def event_create(request):
    if not request.user.can_manage_events:
        raise PermissionDenied(_("Solo planificadores o administradores pueden crear eventos."))
    if request.method == "POST":
        form = EventForm(request.POST, company=request.user.company)
        if form.is_valid():
            event = form.save(commit=False)
            event.company = request.user.company
            event.created_by = request.user
            event.save()
            if request.user.role:
                EventTeamMember.objects.get_or_create(
                    event=event, user=request.user, defaults={"role": request.user.role},
                )
            messages.success(request, _(
                "Evento creado correctamente. Ahora puedes importar el guion/tareas desde Excel."
            ))
            return redirect("tasks:import", event_pk=event.pk)
    else:
        form = EventForm(company=request.user.company)
    return render(request, "events/event_form.html", {"form": form, "is_new": True})


@login_required
def event_edit(request, pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    if request.method == "POST":
        form = EventForm(request.POST, instance=event, company=request.user.company)
        if form.is_valid():
            form.save()
            messages.success(request, _("Evento actualizado."))
            return redirect("events:detail", pk=event.pk)
    else:
        form = EventForm(instance=event, company=request.user.company)
    return render(request, "events/event_form.html", {"form": form, "is_new": False, "event": event})


@login_required
def event_delete(request, pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied(_("Solo planificadores o administradores pueden eliminar eventos."))
    if request.method == "POST":
        name = event.name
        event.delete()
        messages.success(request, _("Evento '%(name)s' eliminado, junto con sus tareas, itinerario y notas.") % {
            "name": name
        })
        return redirect("events:list")
    return render(request, "events/event_confirm_delete.html", {"event": event})


@login_required
def event_detail(request, pk):
    event = get_event_or_403(request.user, pk)
    tasks = event.tasks.select_related("assigned_to", "supervisor")
    if not request.user.can_manage_events:
        tasks = tasks.filter(assigned_to=request.user)
    return render(request, "events/event_detail.html", {
        "event": event,
        "sessions": event.sessions.all(),
        "team_members": event.team_members.select_related("user", "reports_to__user"),
        "tasks": tasks[:10],
        "task_total": event.tasks.count(),
        "vendors": event.event_vendors.select_related("vendor"),
        "notes": event.notes.all()[:5],
        "files": event.files.all()[:5],
        "note_form": NoteForm(),
    })


@login_required
def event_session_create(request, pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    if request.method == "POST":
        form = EventSessionForm(request.POST)
        if form.is_valid():
            session = form.save(commit=False)
            session.event = event
            session.save()
            messages.success(request, _("Actividad agregada al itinerario."))
            return redirect("events:detail", pk=event.pk)
    else:
        form = EventSessionForm(initial={"date": event.event_date})
    return render(request, "events/session_form.html", {"form": form, "event": event, "is_new": True})


@login_required
def event_session_edit(request, pk, session_pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    session = get_object_or_404(EventSession, pk=session_pk, event=event)
    if request.method == "POST":
        form = EventSessionForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            messages.success(request, _("Actividad del itinerario actualizada."))
            return redirect("events:detail", pk=event.pk)
    else:
        form = EventSessionForm(instance=session)
    return render(request, "events/session_form.html", {"form": form, "event": event, "is_new": False})


@login_required
def event_session_delete(request, pk, session_pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    session = get_object_or_404(EventSession, pk=session_pk, event=event)
    if request.method == "POST":
        session.delete()
        messages.success(request, _("Actividad eliminada del itinerario."))
    return redirect("events:detail", pk=event.pk)


@login_required
def event_session_bulk_delete(request, pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    if request.method == "POST":
        session_ids = request.POST.getlist("session_ids")
        deleted, _details = EventSession.objects.filter(event=event, pk__in=session_ids).delete()
        if deleted:
            messages.success(request, _("%(count)s actividades del itinerario eliminadas.") % {"count": deleted})
        else:
            messages.error(request, _("No seleccionaste ninguna actividad."))
    return redirect("events:detail", pk=event.pk)


def _row_to_session_payload(row):
    return {
        "title": row.title,
        "notes": row.notes,
        "venue_name": row.venue_name,
        "start_time": row.start_time.strftime("%H:%M") if row.start_time else "",
        "time_is_carried_over": row.time_is_carried_over,
    }


@login_required
def event_session_import(request, pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied(_("Solo planificadores o administradores pueden importar el itinerario."))

    if request.method == "POST":
        form = SessionImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                rows = importers.parse_minuto_a_minuto(form.cleaned_data["file"])
            except ValueError as exc:
                messages.error(request, str(exc))
                return render(request, "events/session_import.html", {"form": form, "event": event})

            if not rows:
                messages.error(request, _("No se encontraron filas para importar en ese archivo."))
                return render(request, "events/session_import.html", {"form": form, "event": event})

            payload = [_row_to_session_payload(r) for r in rows]

            out_of_order = False
            last_time = None
            for row in payload:
                if row["start_time"]:
                    if last_time and row["start_time"] < last_time:
                        out_of_order = True
                    last_time = row["start_time"]

            return render(request, "events/session_import_preview.html", {
                "event": event,
                "rows": payload,
                "payload_json": json.dumps(payload),
                "out_of_order": out_of_order,
            })
    else:
        form = SessionImportForm()
    return render(request, "events/session_import.html", {"form": form, "event": event})


@login_required
def event_session_import_confirm(request, pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied(_("Solo planificadores o administradores pueden importar el itinerario."))
    if request.method != "POST":
        return redirect("events:session_import", pk=event.pk)

    try:
        rows = json.loads(request.POST.get("payload", "[]"))
    except json.JSONDecodeError:
        messages.error(request, _("No se pudo leer la información a importar."))
        return redirect("events:session_import", pk=event.pk)

    next_order = (event.sessions.aggregate(Max("order"))["order__max"] or 0) + 1
    fallback_time = event.start_time or dt_time(0, 0)
    created = 0
    for row in rows:
        start_time = dt_time.fromisoformat(row["start_time"]) if row.get("start_time") else fallback_time
        EventSession.objects.create(
            event=event,
            title=row["title"],
            venue_name=row.get("venue_name", ""),
            date=event.event_date,
            start_time=start_time,
            notes=row.get("notes", ""),
            order=next_order,
        )
        next_order += 1
        created += 1

    messages.success(request, _("Se importaron %(count)s actividades al itinerario.") % {"count": created})
    return redirect("events:detail", pk=event.pk)


@login_required
def event_team(request, pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    if request.method == "POST":
        form = EventTeamMemberForm(request.POST, company=request.user.company, event=event)
        if form.is_valid():
            member = form.save(commit=False)
            member.event = event
            member.save()
            messages.success(request, _("Miembro agregado al equipo del evento."))
            return redirect("events:team", pk=event.pk)
    else:
        form = EventTeamMemberForm(company=request.user.company, event=event)
    return render(request, "events/event_team.html", {
        "event": event,
        "form": form,
        "team_members": event.team_members.select_related("user", "reports_to__user"),
    })


@login_required
def event_team_remove(request, pk, member_pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    member = get_object_or_404(EventTeamMember, pk=member_pk, event=event)
    if request.method == "POST":
        member.delete()
        messages.success(request, _("Miembro removido del equipo."))
    return redirect("events:team", pk=event.pk)


@login_required
def event_wedding_party(request, pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    create_default_wedding_party_list_types(event.company)
    if request.method == "POST":
        form = WeddingPartyMemberForm(request.POST, company=event.company)
        if form.is_valid():
            member = form.save(commit=False)
            member.event = event
            member.save()
            messages.success(request, _("Persona agregada a la lista."))
            return redirect("events:wedding_party", pk=event.pk)
    else:
        form = WeddingPartyMemberForm(company=event.company)
    members = event.wedding_party_members.select_related("list_type")
    list_types = list(WeddingPartyListType.objects.filter(company=event.company))
    for list_type in list_types:
        list_type.member_list = members.filter(list_type=list_type)
    return render(request, "events/wedding_party.html", {
        "event": event,
        "form": form,
        "list_types": list_types,
    })


@login_required
def event_wedding_party_edit(request, pk, member_pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    member = get_object_or_404(WeddingPartyMember, pk=member_pk, event=event)
    if request.method == "POST":
        form = WeddingPartyMemberForm(request.POST, instance=member, company=event.company)
        if form.is_valid():
            form.save()
            messages.success(request, _("Registro actualizado."))
            return redirect("events:wedding_party", pk=event.pk)
    else:
        form = WeddingPartyMemberForm(instance=member, company=event.company)
    return render(request, "events/wedding_party_form.html", {"form": form, "event": event, "member": member})


@login_required
def event_wedding_party_remove(request, pk, member_pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    member = get_object_or_404(WeddingPartyMember, pk=member_pk, event=event)
    if request.method == "POST":
        member.delete()
        messages.success(request, _("Registro eliminado."))
    return redirect("events:wedding_party", pk=event.pk)


@login_required
def wedding_party_type_list(request):
    if not request.user.can_manage_events:
        raise PermissionDenied(_("No tienes permiso para gestionar las listas del cortejo."))
    create_default_wedding_party_list_types(request.user.company)
    list_types = WeddingPartyListType.objects.filter(company=request.user.company)
    return render(request, "events/wedding_party_type_list.html", {"list_types": list_types})


@login_required
def wedding_party_type_create(request):
    if not request.user.can_manage_events:
        raise PermissionDenied(_("No tienes permiso para gestionar las listas del cortejo."))
    if request.method == "POST":
        form = WeddingPartyListTypeForm(request.POST)
        if form.is_valid():
            list_type = form.save(commit=False)
            list_type.company = request.user.company
            list_type.save()
            messages.success(request, _("Lista creada correctamente."))
            return redirect("events:wedding_party_type_list")
    else:
        form = WeddingPartyListTypeForm()
    return render(request, "events/wedding_party_type_form.html", {"form": form, "is_new": True})


@login_required
def wedding_party_type_edit(request, pk):
    if not request.user.can_manage_events:
        raise PermissionDenied(_("No tienes permiso para gestionar las listas del cortejo."))
    list_type = get_object_or_404(WeddingPartyListType, pk=pk, company=request.user.company)
    if request.method == "POST":
        form = WeddingPartyListTypeForm(request.POST, instance=list_type)
        if form.is_valid():
            form.save()
            messages.success(request, _("Lista actualizada correctamente."))
            return redirect("events:wedding_party_type_list")
    else:
        form = WeddingPartyListTypeForm(instance=list_type)
    return render(request, "events/wedding_party_type_form.html", {
        "form": form, "is_new": False, "list_type": list_type,
    })


@login_required
def wedding_party_type_delete(request, pk):
    if not request.user.can_manage_events:
        raise PermissionDenied(_("No tienes permiso para gestionar las listas del cortejo."))
    list_type = get_object_or_404(WeddingPartyListType, pk=pk, company=request.user.company)
    if request.method == "POST":
        if list_type.members.exists():
            messages.error(request, _("No se puede eliminar una lista que todavía tiene personas asignadas."))
        else:
            list_type.delete()
            messages.success(request, _("Lista eliminada."))
    return redirect("events:wedding_party_type_list")


@login_required
def event_processional(request, pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    if request.method == "POST":
        form = ProcessionalEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.event = event
            entry.save()
            messages.success(request, _("Entrada agregada al planograma."))
            return redirect("events:processional", pk=event.pk)
    else:
        next_order = (
            event.processional_entries.filter(phase=ProcessionalEntry.PHASE_ENTRADA)
            .aggregate(Max("order"))["order__max"] or 0
        ) + 1
        form = ProcessionalEntryForm(initial={"order": next_order, "phase": ProcessionalEntry.PHASE_ENTRADA})
    public_url = request.build_absolute_uri(reverse("events:processional_public", args=[event.share_token]))
    entries_entrada = event.processional_entries.filter(phase=ProcessionalEntry.PHASE_ENTRADA)
    entries_salida = event.processional_entries.filter(phase=ProcessionalEntry.PHASE_SALIDA)
    return render(request, "events/processional.html", {
        "event": event, "form": form,
        "entries_entrada": entries_entrada,
        "entries_salida": entries_salida,
        "diagram_entries_entrada": entries_entrada.order_by("order"),
        "diagram_entries_salida": entries_salida.order_by("-order"),
        "public_url": public_url,
    })


@login_required
def event_processional_edit(request, pk, entry_pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    entry = get_object_or_404(ProcessionalEntry, pk=entry_pk, event=event)
    if request.method == "POST":
        form = ProcessionalEntryForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, _("Entrada del planograma actualizada."))
            return redirect("events:processional", pk=event.pk)
    else:
        form = ProcessionalEntryForm(instance=entry)
    return render(request, "events/processional_form.html", {"form": form, "event": event, "entry": entry})


@login_required
def event_processional_remove(request, pk, entry_pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    entry = get_object_or_404(ProcessionalEntry, pk=entry_pk, event=event)
    if request.method == "POST":
        entry.delete()
        messages.success(request, _("Entrada eliminada del planograma."))
    return redirect("events:processional", pk=event.pk)


def processional_public(request, token):
    """Read-only, no-login view of the church processional diagram — the link a
    planner shares with the bride and, from there, over WhatsApp."""
    event = get_object_or_404(Event, share_token=token)
    return render(request, "events/processional_public.html", {
        "event": event,
        "is_public": True,
        "diagram_entries_entrada": event.processional_entries.filter(
            phase=ProcessionalEntry.PHASE_ENTRADA
        ).order_by("order"),
        "diagram_entries_salida": event.processional_entries.filter(
            phase=ProcessionalEntry.PHASE_SALIDA
        ).order_by("-order"),
    })


@login_required
def event_meals(request, pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    if request.method == "POST":
        form = MealCountForm(request.POST)
        if form.is_valid():
            meal = form.save(commit=False)
            meal.event = event
            meal.save()
            messages.success(request, _("Conteo de comida agregado."))
            return redirect("events:meals", pk=event.pk)
    else:
        form = MealCountForm()
    meals = event.meal_counts.all()
    team_meals = meals.filter(group=MealCount.GROUP_TEAM)
    vendor_meals = meals.filter(group=MealCount.GROUP_VENDOR)
    contingency_meals = meals.filter(group=MealCount.GROUP_CONTINGENCY)
    return render(request, "events/meals.html", {
        "event": event,
        "form": form,
        "team_meals": team_meals,
        "vendor_meals": vendor_meals,
        "contingency_meals": contingency_meals,
        "team_total": team_meals.aggregate(Sum("amount"))["amount__sum"] or 0,
        "vendor_total": vendor_meals.aggregate(Sum("amount"))["amount__sum"] or 0,
        "contingency_total": contingency_meals.aggregate(Sum("amount"))["amount__sum"] or 0,
        "grand_total": meals.aggregate(Sum("amount"))["amount__sum"] or 0,
    })


@login_required
def event_meals_edit(request, pk, meal_pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    meal = get_object_or_404(MealCount, pk=meal_pk, event=event)
    if request.method == "POST":
        form = MealCountForm(request.POST, instance=meal)
        if form.is_valid():
            form.save()
            messages.success(request, _("Conteo de comida actualizado."))
            return redirect("events:meals", pk=event.pk)
    else:
        form = MealCountForm(instance=meal)
    return render(request, "events/meals_form.html", {"form": form, "event": event, "meal": meal})


@login_required
def event_meals_remove(request, pk, meal_pk):
    event = get_event_or_403(request.user, pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    meal = get_object_or_404(MealCount, pk=meal_pk, event=event)
    if request.method == "POST":
        meal.delete()
        messages.success(request, _("Conteo de comida eliminado."))
    return redirect("events:meals", pk=event.pk)


@login_required
def report_itinerary(request, pk):
    event = get_event_or_403(request.user, pk)
    return render(request, "events/report_itinerary.html", {
        "event": event, "sessions": event.sessions.all(),
    })


@login_required
def report_tasks(request, pk):
    event = get_event_or_403(request.user, pk)
    tasks = event.tasks.select_related("assigned_to", "vendor", "supervisor").order_by(
        "assigned_to__first_name", "assigned_to__last_name", "category"
    )
    return render(request, "events/report_tasks.html", {"event": event, "tasks": tasks})


@login_required
def report_status_history(request, pk):
    from apps.tasks.models import TaskStatusHistory

    event = get_event_or_403(request.user, pk)
    history = (
        TaskStatusHistory.objects.filter(task__event=event)
        .select_related("task", "changed_by")
        .order_by("-changed_at")
    )
    return render(request, "events/report_status_history.html", {"event": event, "history": history})
