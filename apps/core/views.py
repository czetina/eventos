from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.events.views import events_visible_to
from apps.tasks.models import Task


@login_required
def dashboard(request):
    user = request.user

    if user.is_encargado:
        return redirect("tasks:my_tasks")

    events = events_visible_to(user)
    upcoming_events = events.filter(event_date__gte=timezone.localdate()).order_by("event_date")[:6]

    if user.is_supervisor:
        tasks_qs = Task.objects.filter(supervisor=user)
    else:
        tasks_qs = Task.objects.filter(event__in=events)

    context = {
        "upcoming_events": upcoming_events,
        "total_events": events.count(),
        "pending_tasks": tasks_qs.exclude(status=Task.STATUS_DONE).count(),
        "overdue_tasks": [t for t in tasks_qs.exclude(status=Task.STATUS_DONE) if t.is_overdue][:8],
        "team_size": user.company.users.count() if user.company else 0,
    }
    return render(request, "core/dashboard.html", context)
