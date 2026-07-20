from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Company
from apps.events.models import Event


class VendorCategory(models.Model):
    """A company-maintained vendor/venue category (e.g. Banquete, Flores,
    Limpieza, Maquillaje, Alquileres, Seguridad) — same 'Mantenimiento'
    pattern as Role/WeddingPartyListType/EventSectionType."""

    company = models.ForeignKey(
        Company, verbose_name=_("empresa"), related_name="vendor_categories", on_delete=models.CASCADE
    )
    name = models.CharField(_("nombre de la categoría"), max_length=100)
    order = models.PositiveIntegerField(_("orden"), default=0)

    class Meta:
        verbose_name = _("categoría de proveedor")
        verbose_name_plural = _("mantenimiento de categorías de proveedores")
        unique_together = [("company", "name")]
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


DEFAULT_VENDOR_CATEGORIES = [
    "Espacio / Venue", "Banquete", "Flores", "Música", "Fotografía / Video",
    "Licor / Bebidas", "Mobiliario", "Transporte", "Decoración",
    "Limpieza", "Maquillaje", "Alquileres", "Seguridad", "Otro",
]


def create_default_vendor_categories(company):
    """Lazily called wherever vendor categories are used, so both new and
    already-existing companies end up with the standard categories without
    a data migration."""
    categories = {}
    for order, name in enumerate(DEFAULT_VENDOR_CATEGORIES):
        category, _created = VendorCategory.objects.get_or_create(
            company=company, name=name, defaults={"order": order}
        )
        categories[name] = category
    return categories


class Vendor(models.Model):
    """A vendor or venue (proveedor / espacio) reusable across events of a company."""

    company = models.ForeignKey(
        Company, verbose_name=_("empresa"), related_name="vendors", on_delete=models.CASCADE
    )
    name = models.CharField(_("nombre"), max_length=200)
    category = models.ForeignKey(
        VendorCategory, verbose_name=_("categoría"), related_name="vendors", on_delete=models.CASCADE,
    )
    contact_name = models.CharField(_("contacto"), max_length=150, blank=True)
    phone = models.CharField(_("teléfono"), max_length=40, blank=True)
    email = models.EmailField(_("correo"), blank=True)
    notes = models.TextField(_("notas"), blank=True)
    is_active = models.BooleanField(
        _("activo"), default=True,
        help_text=_("Un proveedor dado de baja no se puede elegir para nuevas asignaciones."),
    )
    deactivated_on = models.DateField(_("fecha de baja"), null=True, blank=True)
    created_at = models.DateTimeField(_("creado"), auto_now_add=True)

    class Meta:
        verbose_name = _("proveedor / espacio")
        verbose_name_plural = _("proveedores y espacios")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.category})"


class EventVendor(models.Model):
    """Booking of a vendor/venue for a specific event, with contract details."""

    STATUS_QUOTE = "cotizacion"
    STATUS_CONFIRMED = "confirmado"
    STATUS_PAID = "pagado"
    STATUS_CANCELLED = "cancelado"

    STATUS_CHOICES = [
        (STATUS_QUOTE, _("Cotización")),
        (STATUS_CONFIRMED, _("Confirmado")),
        (STATUS_PAID, _("Pagado")),
        (STATUS_CANCELLED, _("Cancelado")),
    ]

    event = models.ForeignKey(
        Event, verbose_name=_("evento"), related_name="event_vendors", on_delete=models.CASCADE
    )
    vendor = models.ForeignKey(
        Vendor, verbose_name=_("proveedor"), related_name="event_bookings", on_delete=models.CASCADE
    )
    contract_amount = models.DecimalField(
        _("monto del contrato"), max_digits=12, decimal_places=2, default=0
    )
    deposit_paid = models.DecimalField(
        _("total abonado"), max_digits=12, decimal_places=2, default=0,
        help_text=_("Se recalcula automáticamente a partir de los abonos registrados."),
    )
    status = models.CharField(
        _("estado"), max_length=20, choices=STATUS_CHOICES, default=STATUS_QUOTE
    )
    notes = models.TextField(_("notas"), blank=True)
    created_at = models.DateTimeField(_("creado"), auto_now_add=True)

    class Meta:
        verbose_name = _("proveedor del evento")
        verbose_name_plural = _("proveedores del evento")
        unique_together = [("event", "vendor")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.vendor} - {self.event}"

    @property
    def balance_due(self):
        return self.contract_amount - self.deposit_paid

    @property
    def is_fully_paid(self):
        return self.contract_amount > 0 and self.balance_due <= 0

    def recompute_deposit_paid(self):
        total = self.payments.aggregate(models.Sum("amount"))["amount__sum"] or 0
        self.deposit_paid = total
        self.save(update_fields=["deposit_paid"])


def vendor_payment_document_upload_path(instance, filename):
    return f"proveedores/abonos/evento_{instance.event_vendor.event_id}/{filename}"


class VendorPayment(models.Model):
    """One installment (abono) paid toward an EventVendor's contract. A vendor
    can be paid off in several installments up to the contract balance; once
    the balance reaches zero, uploading a supporting document is required."""

    event_vendor = models.ForeignKey(
        EventVendor, verbose_name=_("proveedor del evento"), related_name="payments", on_delete=models.CASCADE
    )
    date = models.DateField(_("fecha"))
    amount = models.DecimalField(_("monto"), max_digits=12, decimal_places=2)
    document = models.FileField(
        _("documento"), upload_to=vendor_payment_document_upload_path, blank=True, null=True,
        help_text=_("Requerido cuando este abono completa el saldo del proveedor."),
    )
    note = models.CharField(_("nota"), max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("registrado por"), related_name="vendor_payments_recorded",
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    created_at = models.DateTimeField(_("creado"), auto_now_add=True)

    class Meta:
        verbose_name = _("abono a proveedor")
        verbose_name_plural = _("abonos a proveedores")
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.event_vendor} — {self.amount}"
