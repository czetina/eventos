from datetime import date, time as dt_time

from django.db import migrations


def _date_rank(task):
    """Same rule as apps.tasks.models._chain_date_rank, duplicated here
    against plain field values (not the real model's properties/methods,
    which historical migration models don't have)."""
    if task.status == "completada":
        return -(task.completed_at.timestamp() if task.completed_at else 0)
    return (task.due_date or date.max, task.due_time or dt_time.max)


def resort_existing_chains(apps, schema_editor):
    """One-time backfill: puts every existing chain's tasks into the new
    auto-sort order (completadas primero por fecha reciente, luego en
    progreso, luego pendientes por fecha/hora) the first time this deploys,
    so chains created before this feature don't wait for a status/date
    change on one of their tasks to display correctly. From here on,
    relocate_task_in_chain() keeps individual changes correctly placed
    while preserving manual subir/bajar adjustments for everything else."""
    TaskChain = apps.get_model("tasks", "TaskChain")
    Task = apps.get_model("tasks", "Task")
    for chain in TaskChain.objects.all():
        tasks = list(chain.tasks.all())
        if not tasks:
            continue
        buckets = {0: [], 1: [], 2: []}
        for t in tasks:
            if t.status == "completada":
                buckets[0].append(t)
            elif t.status == "en_progreso":
                buckets[1].append(t)
            else:
                buckets[2].append(t)
        for bucket_tasks in buckets.values():
            bucket_tasks.sort(key=_date_rank)
        ordered = buckets[0] + buckets[1] + buckets[2]
        # Two-phase update — NULL is exempt from unique_chain_order_per_chain,
        # so staging every row through NULL first avoids a transient collision
        # with another row that hasn't been renumbered yet.
        Task.objects.filter(pk__in=[t.pk for t in ordered]).update(chain_order=None)
        for i, t in enumerate(ordered, start=1):
            Task.objects.filter(pk=t.pk).update(chain_order=i)


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0005_task_is_guion_cliente"),
    ]

    operations = [
        migrations.RunPython(resort_existing_chains, migrations.RunPython.noop),
    ]
