from django.db import migrations


def backfill_payments(apps, schema_editor):
    EventVendor = apps.get_model("vendors", "EventVendor")
    VendorPayment = apps.get_model("vendors", "VendorPayment")
    for ev in EventVendor.objects.exclude(deposit_paid=0):
        VendorPayment.objects.create(
            event_vendor=ev,
            date=ev.created_at.date(),
            amount=ev.deposit_paid,
            note="Migrado desde el campo anterior de anticipo pagado.",
        )


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0003_alter_eventvendor_deposit_paid_vendorpayment"),
    ]

    operations = [
        migrations.RunPython(backfill_payments, migrations.RunPython.noop),
    ]
