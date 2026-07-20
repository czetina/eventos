import django.db.models.deletion
from django.db import migrations, models


def populate_section_types(apps, schema_editor):
    Company = apps.get_model("accounts", "Company")
    EventSectionType = apps.get_model("events", "EventSectionType")
    EventSession = apps.get_model("events", "EventSession")

    SECTION_LABELS = {
        "ceremonia": "Ceremonia",
        "recepcion": "Recepción",
        "montaje": "Montaje",
        "desmontaje": "Desmontaje",
        "otro": "Otro",
    }
    DEFAULT_ORDER = {"Ceremonia": 0, "Recepción": 1, "Montaje": 2, "Desmontaje": 3, "Otro": 4}

    type_cache = {}

    def get_type(company_id, name):
        key = (company_id, name)
        if key not in type_cache:
            obj, _created = EventSectionType.objects.get_or_create(
                company_id=company_id, name=name, defaults={"order": DEFAULT_ORDER.get(name, 99)}
            )
            type_cache[key] = obj
        return type_cache[key]

    for company in Company.objects.all():
        for name in DEFAULT_ORDER:
            get_type(company.id, name)

    for session in EventSession.objects.select_related("event").all():
        label = SECTION_LABELS.get(session.section, "Otro")
        session.section_new_id = get_type(session.event.company_id, label).id
        session.save(update_fields=["section_new"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("events", "0003_alter_mealcount_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventSectionType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, verbose_name="nombre de la sección")),
                ("order", models.PositiveIntegerField(default=0, verbose_name="orden")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="section_types", to="accounts.company", verbose_name="empresa")),
            ],
            options={
                "verbose_name": "sección de itinerario",
                "verbose_name_plural": "mantenimiento de secciones",
                "ordering": ["order", "name"],
                "unique_together": {("company", "name")},
            },
        ),
        migrations.AddField(
            model_name="eventsession",
            name="section_new",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name="sessions", to="events.eventsectiontype", verbose_name="sección"),
        ),
        migrations.RunPython(populate_section_types, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="eventsession",
            name="section",
        ),
        migrations.RenameField(
            model_name="eventsession",
            old_name="section_new",
            new_name="section",
        ),
        migrations.AlterField(
            model_name="eventsession",
            name="section",
            field=models.ForeignKey(help_text="Para agrupar el itinerario en reportes: ceremonia, recepción, montaje, desmontaje", on_delete=django.db.models.deletion.CASCADE, related_name="sessions", to="events.eventsectiontype", verbose_name="sección"),
        ),
    ]
