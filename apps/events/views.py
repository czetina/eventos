from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from django.utils.translation import gettext_lazy as _

from .forms import EventForm, EventSessionForm, EventTeamMemberForm
from .models import Event, EventSession, EventTeamMember


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
            EventTeamMember.objects.get_or_create(
                event=event, user=request.user,
                defaults={"role_in_event": EventTeamMember.ROLE_PLANNER},
            )
            messages.success(request, _("Evento creado correctamente."))
            return redirect("events:detail", pk=event.pk)
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
        form = EventSessionForm()
    return render(request, "events/session_form.html", {"form": form, "event": event})


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
