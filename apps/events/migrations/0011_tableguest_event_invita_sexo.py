import django.db.models.deletion
from django.db import migrations, models


def backfill_guest_event(apps, schema_editor):
    TableGuest = apps.get_model("events", "TableGuest")
    for guest in TableGuest.objects.select_related("table").filter(event__isnull=True):
        guest.event_id = guest.table.event_id
        guest.save(update_fields=["event"])


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0010_table_guest_speech"),
    ]

    operations = [
        migrations.AddField(
            model_name="tableguest",
            name="event",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="all_guests",
                to="events.event",
                verbose_name="evento",
            ),
        ),
        migrations.RunPython(backfill_guest_event, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="tableguest",
            name="event",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="all_guests",
                to="events.event",
                verbose_name="evento",
            ),
        ),
        migrations.AlterField(
            model_name="tableguest",
            name="table",
            field=models.ForeignKey(
                blank=True,
                help_text="Vacío si el invitado todavía no tiene mesa asignada.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="guests",
                to="events.seatingtable",
                verbose_name="mesa",
            ),
        ),
        migrations.AddField(
            model_name="tableguest",
            name="invita",
            field=models.CharField(
                blank=True,
                choices=[("novio", "Novio"), ("novia", "Novia"), ("ambos", "Ambos")],
                max_length=10,
                verbose_name="invita",
            ),
        ),
        migrations.AddField(
            model_name="tableguest",
            name="sexo",
            field=models.CharField(
                blank=True,
                choices=[("hombre", "Hombre"), ("mujer", "Mujer"), ("nino", "Niño"), ("nina", "Niña")],
                max_length=10,
                verbose_name="sexo",
            ),
        ),
    ]
