from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Company
from apps.events.models import Event


class Vendor(models.Model):
    """A vendor or venue (proveedor / espacio) reusable across events of a company."""

    CATEGORY_VENUE = "espacio"
    CATEGORY_CATERING = "banquete"
    CATEGORY_FLOWERS = "flores"
    CATEGORY_MUSIC = "musica"
    CATEGORY_PHOTO = "fotografia"
    CATEGORY_LIQUOR = "licor"
    CATEGORY_FURNITURE = "mobiliario"
    CATEGORY_TRANSPORT = "transporte"
    CATEGORY_DECOR = "decoracion"
    CATEGORY_OTHER = "otro"

    CATEGORY_CHOICES = [
        (CATEGORY_VENUE, _("Espacio / Venue")),
        (CATEGORY_CATERING, _("Banquete")),
        (CATEGORY_FLOWERS, _("Flores")),
        (CATEGORY_MUSIC, _("Música")),
        (CATEGORY_PHOTO, _("Fotografía / Video")),
        (CATEGORY_LIQUOR, _("Licor / Bebidas")),
        (CATEGORY_FURNITURE, _("Mobiliario")),
        (CATEGORY_TRANSPORT, _("Transporte")),
        (CATEGORY_DECOR, _("Decoración")),
        (CATEGORY_OTHER, _("Otro")),
    ]

    company = models.ForeignKey(
        Company, verbose_name=_("empresa"), related_name="vendors", on_delete=models.CASCADE
    )
    name = models.CharField(_("nombre"), max_length=200)
    category = models.CharField(
        _("categoría"), max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER
    )
    contact_name = models.CharField(_("contacto"), max_length=150, blank=True)
    phone = models.CharField(_("teléfono"), max_length=40, blank=True)
    email = models.EmailField(_("correo"), blank=True)
    notes = models.TextField(_("notas"), blank=True)
    created_at = models.DateTimeField(_("creado"), auto_now_add=True)

    class Meta:
        verbose_name = _("proveedor / espacio")
        verbose_name_plural = _("proveedores y espacios")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


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
        _("anticipo pagado"), max_digits=12, decimal_places=2, default=0
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
