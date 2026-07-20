import django.db.models.deletion
from django.db import migrations, models


def populate_vendor_categories(apps, schema_editor):
    Company = apps.get_model("accounts", "Company")
    VendorCategory = apps.get_model("vendors", "VendorCategory")
    Vendor = apps.get_model("vendors", "Vendor")

    CATEGORY_LABELS = {
        "espacio": "Espacio / Venue",
        "banquete": "Banquete",
        "flores": "Flores",
        "musica": "Música",
        "fotografia": "Fotografía / Video",
        "licor": "Licor / Bebidas",
        "mobiliario": "Mobiliario",
        "transporte": "Transporte",
        "decoracion": "Decoración",
        "otro": "Otro",
    }
    DEFAULT_NAMES = [
        "Espacio / Venue", "Banquete", "Flores", "Música", "Fotografía / Video",
        "Licor / Bebidas", "Mobiliario", "Transporte", "Decoración",
        "Limpieza", "Maquillaje", "Alquileres", "Seguridad", "Otro",
    ]

    type_cache = {}

    def get_category(company_id, name):
        key = (company_id, name)
        if key not in type_cache:
            obj, _created = VendorCategory.objects.get_or_create(
                company_id=company_id, name=name, defaults={"order": DEFAULT_NAMES.index(name)}
            )
            type_cache[key] = obj
        return type_cache[key]

    for company in Company.objects.all():
        for name in DEFAULT_NAMES:
            get_category(company.id, name)

    for vendor in Vendor.objects.all():
        label = CATEGORY_LABELS.get(vendor.category, "Otro")
        vendor.category_new_id = get_category(vendor.company_id, label).id
        vendor.save(update_fields=["category_new"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("vendors", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="VendorCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, verbose_name="nombre de la categoría")),
                ("order", models.PositiveIntegerField(default=0, verbose_name="orden")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vendor_categories", to="accounts.company", verbose_name="empresa")),
            ],
            options={
                "verbose_name": "categoría de proveedor",
                "verbose_name_plural": "mantenimiento de categorías de proveedores",
                "ordering": ["order", "name"],
                "unique_together": {("company", "name")},
            },
        ),
        migrations.AddField(
            model_name="vendor",
            name="category_new",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name="vendors", to="vendors.vendorcategory", verbose_name="categoría"),
        ),
        migrations.AddField(
            model_name="vendor",
            name="is_active",
            field=models.BooleanField(default=True, help_text="Un proveedor dado de baja no se puede elegir para nuevas asignaciones.", verbose_name="activo"),
        ),
        migrations.AddField(
            model_name="vendor",
            name="deactivated_on",
            field=models.DateField(blank=True, null=True, verbose_name="fecha de baja"),
        ),
        migrations.RunPython(populate_vendor_categories, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="vendor",
            name="category",
        ),
        migrations.RenameField(
            model_name="vendor",
            old_name="category_new",
            new_name="category",
        ),
        migrations.AlterField(
            model_name="vendor",
            name="category",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vendors", to="vendors.vendorcategory", verbose_name="categoría"),
        ),
    ]
