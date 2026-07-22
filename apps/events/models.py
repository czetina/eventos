import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField

from apps.accounts.models import Company, Role


class Event(models.Model):
    """A single event (wedding, corporate event, birthday, etc.)."""

    TYPE_WEDDING = "boda"
    TYPE_CORPORATE = "corporativo"
    TYPE_BIRTHDAY = "cumpleanos"
    TYPE_SOCIAL = "social"
    TYPE_OTHER = "otro"

    EVENT_TYPE_CHOICES = [
        (TYPE_WEDDING, _("Boda")),
        (TYPE_CORPORATE, _("Evento corporativo")),
        (TYPE_BIRTHDAY, _("Cumpleaños")),
        (TYPE_SOCIAL, _("Evento social")),
        (TYPE_OTHER, _("Otro")),
    ]

    STATUS_PLANNING = "planificacion"
    STATUS_CONFIRMED = "confirmado"
    STATUS_IN_PROGRESS = "en_curso"
    STATUS_DONE = "finalizado"
    STATUS_CANCELLED = "cancelado"

    STATUS_CHOICES = [
        (STATUS_PLANNING, _("En planificación")),
        (STATUS_CONFIRMED, _("Confirmado")),
        (STATUS_IN_PROGRESS, _("En curso")),
        (STATUS_DONE, _("Finalizado")),
        (STATUS_CANCELLED, _("Cancelado")),
    ]

    company = models.ForeignKey(
        Company, verbose_name=_("empresa"), related_name="events", on_delete=models.CASCADE
    )
    name = models.CharField(_("nombre del evento"), max_length=200)
    event_type = models.CharField(
        _("tipo de evento"), max_length=20, choices=EVENT_TYPE_CHOICES, default=TYPE_WEDDING
    )
    client_name = models.CharField(_("cliente"), max_length=200)
    client_phone = models.CharField(_("teléfono del cliente"), max_length=40, blank=True)
    client_email = models.EmailField(_("correo del cliente"), blank=True)

    country = CountryField(_("país"), blank_label=_("(selecciona un país)"))
    city = models.CharField(_("ciudad"), max_length=120, blank=True)
    venue_name = models.CharField(_("espacio / lugar principal"), max_length=200, blank=True)
    venue_address = models.CharField(_("dirección"), max_length=255, blank=True)
    civil_ceremony_venue = models.CharField(_("lugar de la ceremonia civil"), max_length=200, blank=True)
    religious_ceremony_venue = models.CharField(
        _("lugar de la ceremonia eclesiástica"), max_length=200, blank=True
    )
    cocktail_venue = models.CharField(_("lugar del cóctel"), max_length=200, blank=True)

    event_date = models.DateField(_("fecha del evento"))
    start_time = models.TimeField(_("hora de inicio"), null=True, blank=True)
    end_time = models.TimeField(_("hora de fin"), null=True, blank=True)

    status = models.CharField(
        _("estado"), max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANNING
    )
    description = models.TextField(_("descripción"), blank=True)

    planner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("planificador a cargo"),
        related_name="events_planned",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("creado por"),
        related_name="events_created",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(_("creado"), auto_now_add=True)
    updated_at = models.DateTimeField(_("actualizado"), auto_now=True)

    share_token = models.UUIDField(
        _("token para compartir"), default=uuid.uuid4, editable=False, unique=True,
        help_text=_("Identificador usado para el link público (sin login) del planograma del cortejo."),
    )

    class Meta:
        verbose_name = _("evento")
        verbose_name_plural = _("eventos")
        ordering = ["-event_date", "name"]

    def __str__(self):
        return f"{self.name} ({self.event_date})"

    def get_absolute_url(self):
        return reverse("events:detail", args=[self.pk])

    @property
    def task_progress_percent(self):
        total = self.tasks.count()
        if not total:
            return 0
        done = self.tasks.filter(status="completada").count()
        return round(done * 100 / total)

    @property
    def total_expenses(self):
        return self.expenses.aggregate(models.Sum("amount"))["amount__sum"] or 0

    @property
    def advance_amount(self):
        return self.advances.aggregate(models.Sum("amount"))["amount__sum"] or 0

    @property
    def expense_balance(self):
        """Anticipo menos lo gastado. Negativo = hay que cobrarle más al cliente."""
        return self.advance_amount - self.total_expenses


class EventSectionType(models.Model):
    """A company-maintained itinerary section/area (e.g. Ceremonia, Recepción,
    Montaje, Desmontaje, Otro) used to group EventSession rows in reports —
    same 'Mantenimiento' pattern as WeddingPartyListType/VendorCategory, so a
    company can add its own areas instead of being stuck with the defaults."""

    company = models.ForeignKey(
        Company, verbose_name=_("empresa"), related_name="section_types", on_delete=models.CASCADE
    )
    name = models.CharField(_("nombre de la sección"), max_length=100)
    order = models.PositiveIntegerField(_("orden"), default=0)

    class Meta:
        verbose_name = _("sección de itinerario")
        verbose_name_plural = _("mantenimiento de secciones")
        unique_together = [("company", "name")]
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


DEFAULT_SECTION_TYPES = ["Ceremonia", "Recepción", "Montaje", "Desmontaje", "Otro"]

# Maps the plain-string section codes produced by apps.tasks.importers (framework-free,
# so it can't reference this model directly) to the default section type names above.
IMPORTER_SECTION_CODE_TO_NAME = {
    "ceremonia": "Ceremonia",
    "recepcion": "Recepción",
    "montaje": "Montaje",
    "desmontaje": "Desmontaje",
    "otro": "Otro",
}


def create_default_section_types(company):
    """Lazily called wherever itinerary sections are used, so both new and
    already-existing companies end up with the standard areas without a
    data migration."""
    types = {}
    for order, name in enumerate(DEFAULT_SECTION_TYPES):
        section_type, _created = EventSectionType.objects.get_or_create(
            company=company, name=name, defaults={"order": order}
        )
        types[name] = section_type
    return types


class EventSession(models.Model):
    """A time block within an event's itinerary (ceremony, cocktail, reception...),
    each with its own date, potentially at a different venue. Supports multi-day
    events (rehearsal, montaje, the event day itself, desmontaje) as well as
    multiple happenings on the same day."""

    event = models.ForeignKey(
        Event, verbose_name=_("evento"), related_name="sessions", on_delete=models.CASCADE
    )
    section = models.ForeignKey(
        EventSectionType, verbose_name=_("sección"), related_name="sessions", on_delete=models.CASCADE,
        help_text=_("Para agrupar el itinerario en reportes: ceremonia, recepción, montaje, desmontaje"),
    )
    title = models.CharField(_("actividad"), max_length=150)
    venue_name = models.CharField(_("lugar"), max_length=200, blank=True)
    address = models.CharField(_("dirección"), max_length=255, blank=True)
    date = models.DateField(_("fecha"))
    start_time = models.TimeField(_("hora de inicio"))
    end_time = models.TimeField(_("hora de fin"), null=True, blank=True)
    notes = models.TextField(_("notas"), blank=True)
    order = models.PositiveIntegerField(_("orden"), default=0)

    class Meta:
        verbose_name = _("actividad del itinerario")
        verbose_name_plural = _("itinerario")
        ordering = ["date", "order", "start_time"]

    def __str__(self):
        return f"{self.title} - {self.date} {self.start_time}"


class EventTeamMember(models.Model):
    """Assigns a user to an event with a role and an optional supervisor, modeling
    the hierarchy (supervisor / encargado) for that specific event. The role is one
    of the company's custom Roles (Mantenimiento de roles) — its base_level already
    carries the permission tier, so nothing else needs to model that separately."""

    event = models.ForeignKey(
        Event, verbose_name=_("evento"), related_name="team_members", on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("usuario"),
        related_name="event_memberships",
        on_delete=models.CASCADE,
    )
    role = models.ForeignKey(
        Role, verbose_name=_("rol"), related_name="event_memberships", on_delete=models.CASCADE,
    )
    area = models.CharField(
        _("área / responsabilidad"), max_length=120, blank=True,
        help_text=_("Ej. Banquete, Sonido, Decoración, Logística"),
    )
    reports_to = models.ForeignKey(
        "self",
        verbose_name=_("reporta a"),
        related_name="direct_reports",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    joined_at = models.DateTimeField(_("asignado desde"), auto_now_add=True)

    class Meta:
        verbose_name = _("miembro del equipo del evento")
        verbose_name_plural = _("equipo del evento")
        unique_together = [("event", "user")]
        ordering = ["role__name", "area"]

    def __str__(self):
        return f"{self.user} - {self.role} ({self.event})"


class WeddingPartyListType(models.Model):
    """A company-maintained category for the wedding party list (e.g. Boutonnieres,
    Damas, Discursos, Ramo de Dama, Novia, Novio, Caballeros). Kept as its own
    model — rather than a fixed choices list — so each company can add/rename/
    reorder categories via 'Mantenimiento de listas del cortejo', the same
    pattern used for company-custom Roles."""

    company = models.ForeignKey(
        Company, verbose_name=_("empresa"), related_name="wedding_party_list_types", on_delete=models.CASCADE
    )
    name = models.CharField(_("nombre de la lista"), max_length=100)
    order = models.PositiveIntegerField(_("orden"), default=0)

    class Meta:
        verbose_name = _("lista del cortejo")
        verbose_name_plural = _("mantenimiento de listas del cortejo")
        unique_together = [("company", "name")]
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


DEFAULT_WEDDING_PARTY_LIST_TYPES = [
    "Boutonnieres", "Damas", "Discursos", "Ramo de Dama", "Novia", "Novio", "Caballeros",
]


def create_default_wedding_party_list_types(company):
    """Lazily called wherever the cortejo lists are used, so both new and
    already-existing companies end up with the standard categories without
    needing a data migration."""
    types = {}
    for order, name in enumerate(DEFAULT_WEDDING_PARTY_LIST_TYPES):
        list_type, _created = WeddingPartyListType.objects.get_or_create(
            company=company, name=name, defaults={"order": order}
        )
        types[name] = list_type
    return types


class WeddingPartyMember(models.Model):
    """A person in the wedding party lists a planner tracks for a Catholic ceremony:
    who needs a boutonniere, who's a bridesmaid, who gives a speech and at which
    table. Kept as one model since the lists share the same basic shape; which
    list it belongs to is a company-maintained WeddingPartyListType."""

    event = models.ForeignKey(
        Event, verbose_name=_("evento"), related_name="wedding_party_members", on_delete=models.CASCADE
    )
    list_type = models.ForeignKey(
        WeddingPartyListType, verbose_name=_("lista"), related_name="members", on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField(_("cantidad"), default=1)
    name = models.CharField(_("nombre"), max_length=150)
    role_description = models.CharField(
        _("rol / descripción"), max_length=150, blank=True,
        help_text=_("Ej. 'Corte', 'FATHER OF THE GROOM', 'ROBERT BROTHER'S'"),
    )
    order = models.PositiveIntegerField(_("orden"), default=0)
    table_number = models.CharField(_("mesa"), max_length=20, blank=True)
    notes = models.CharField(_("notas"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("miembro del cortejo")
        verbose_name_plural = _("cortejo nupcial")
        ordering = ["list_type__order", "order", "name"]

    def __str__(self):
        return f"{self.name} ({self.list_type})"


class WeddingTableType(models.Model):
    """A company-maintained table shape/style (e.g. Redonda, Cuadrada,
    Rectangular, Imperial, Coctelera) — same 'Mantenimiento' pattern as
    WeddingPartyListType/VendorCategory."""

    company = models.ForeignKey(
        Company, verbose_name=_("empresa"), related_name="table_types", on_delete=models.CASCADE
    )
    name = models.CharField(_("nombre"), max_length=100)
    order = models.PositiveIntegerField(_("orden"), default=0)

    class Meta:
        verbose_name = _("tipo de mesa")
        verbose_name_plural = _("mantenimiento de tipos de mesa")
        unique_together = [("company", "name")]
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


DEFAULT_TABLE_TYPES = ["Redonda", "Cuadrada", "Rectangular", "Imperial", "Coctelera"]


def create_default_table_types(company):
    types = {}
    for order, name in enumerate(DEFAULT_TABLE_TYPES):
        table_type, _created = WeddingTableType.objects.get_or_create(
            company=company, name=name, defaults={"order": order}
        )
        types[name] = table_type
    return types


class SeatingTable(models.Model):
    """One table in the event's seating chart (plan de mesas): its number,
    shape/type, seat capacity, and the guests assigned to it."""

    event = models.ForeignKey(
        Event, verbose_name=_("evento"), related_name="seating_tables", on_delete=models.CASCADE
    )
    table_number = models.CharField(_("número de mesa"), max_length=20)
    table_type = models.ForeignKey(
        WeddingTableType, verbose_name=_("tipo de mesa"), related_name="tables", on_delete=models.CASCADE
    )
    capacity = models.PositiveIntegerField(_("capacidad (personas)"), default=8)
    notes = models.CharField(_("notas"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("mesa")
        verbose_name_plural = _("plan de mesas")
        ordering = ["table_number"]

    def __str__(self):
        return f"Mesa {self.table_number}"

    @property
    def guest_count(self):
        return self.guests.count()

    @property
    def is_over_capacity(self):
        return self.guest_count > self.capacity


class TableGuest(models.Model):
    table = models.ForeignKey(
        SeatingTable, verbose_name=_("mesa"), related_name="guests", on_delete=models.CASCADE
    )
    name = models.CharField(_("nombre"), max_length=150)
    notes = models.CharField(_("notas"), max_length=255, blank=True)
    order = models.PositiveIntegerField(_("orden"), default=0)
    gives_speech = models.BooleanField(_("da discurso"), default=False)
    speech_member = models.ForeignKey(
        "WeddingPartyMember", verbose_name=_("registro en discursos"), null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
        help_text=_("Registro creado automáticamente en Cortejo nupcial › Discursos."),
    )

    class Meta:
        verbose_name = _("invitado")
        verbose_name_plural = _("invitados")
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class ProcessionalEntry(models.Model):
    """One step of the church processional order — who enters (or exits) on
    each side of the aisle (plus an optional center position for someone who
    walks alone down the middle), in walking order, feeding the auto-generated
    top-down diagram used for the ceremony rehearsal.

    For the 'entrada' phase, the altar is drawn at the top and the church
    doors at the bottom: order=1 is shown right at the altar and the last
    order at the entrance, matching the direction people actually walk in.

    For the 'salida' phase the diagram is flipped — the doors are drawn at
    the top and the altar at the bottom, since order=1 (first to walk out)
    ends up closest to the door and the highest order (last to leave the
    altar) stays near the altar. Order 0 is reserved for a fixed reference
    at the altar that doesn't walk out (e.g. the officiant) and is always
    placed last/closest to the altar regardless of everyone else's order."""

    PHASE_ENTRADA = "entrada"
    PHASE_SALIDA = "salida"

    PHASE_CHOICES = [
        (PHASE_ENTRADA, _("Entrada")),
        (PHASE_SALIDA, _("Salida")),
    ]

    event = models.ForeignKey(
        Event, verbose_name=_("evento"), related_name="processional_entries", on_delete=models.CASCADE
    )
    phase = models.CharField(_("fase"), max_length=10, choices=PHASE_CHOICES, default=PHASE_ENTRADA)
    order = models.PositiveIntegerField(_("orden de entrada"), default=0)
    left_name = models.CharField(_("lado izquierdo"), max_length=200, blank=True)
    center_name = models.CharField(_("centro"), max_length=200, blank=True)
    right_name = models.CharField(_("lado derecho"), max_length=200, blank=True)
    detail = models.CharField(_("detalle"), max_length=255, blank=True)
    detail_visible_public = models.BooleanField(
        _("mostrar el detalle en el enlace público"), default=True,
        help_text=_("Desactívalo si esta nota es solo para uso interno del equipo de planificación."),
    )
    music = models.CharField(_("música"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("entrada del cortejo")
        verbose_name_plural = _("orden del cortejo (planograma)")
        ordering = ["phase", "order"]

    def __str__(self):
        return f"#{self.order}: {self.left_name} / {self.right_name}"


class MealCount(models.Model):
    """Headcount (and cost) of crew/vendor meals a planner needs to arrange for
    an event — separate from the guest catering, which is tracked via Vendor
    bookings. Each row can point at a specific vendor or team member (free
    text, since not every 'asistente 1' has a formal user account) so the
    breakdown matches how a planner actually tracks it, e.g. 'Proveedor
    Transportes, comida, 2, $200' or 'Equipo interno, Planner, cena, 1, $500'."""

    GROUP_TEAM = "equipo"
    GROUP_VENDOR = "proveedores"
    GROUP_CONTINGENCY = "imprevistos"

    GROUP_CHOICES = [
        (GROUP_TEAM, _("Equipo interno")),
        (GROUP_VENDOR, _("Proveedores")),
        (GROUP_CONTINGENCY, _("Imprevistos")),
    ]

    event = models.ForeignKey(
        Event, verbose_name=_("evento"), related_name="meal_counts", on_delete=models.CASCADE
    )
    group = models.CharField(_("grupo"), max_length=20, choices=GROUP_CHOICES, default=GROUP_TEAM)
    target_name = models.CharField(
        _("proveedor / persona"), max_length=150, blank=True,
        help_text=_("Ej. 'Transportes', 'Asistente 1', 'Planner'"),
    )
    meal_label = models.CharField(
        _("comida"), max_length=100, help_text=_("Ej. Almuerzo, Cena, Snack box")
    )
    count = models.PositiveIntegerField(_("cantidad"), default=0)
    amount = models.DecimalField(_("monto"), max_digits=10, decimal_places=2, default=0)
    notes = models.CharField(_("notas"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("conteo de comida")
        verbose_name_plural = _("comidas de equipo y proveedores")
        ordering = ["group", "target_name", "meal_label"]

    def __str__(self):
        return f"{self.meal_label} ({self.get_group_display()}): {self.count}"


def expense_document_upload_path(instance, filename):
    return f"gastos/evento_{instance.event_id}/{filename}"


class Expense(models.Model):
    """A real, one-off expense paid out for the event (not a vendor contract —
    those are tracked via EventVendor/VendorPayment). Balanced against the
    event's advance_amount so the planner can see at a glance whether there's
    still money left from the anticipo or whether the client needs to be
    charged more."""

    event = models.ForeignKey(
        Event, verbose_name=_("evento"), related_name="expenses", on_delete=models.CASCADE
    )
    date = models.DateField(_("fecha"))
    description = models.CharField(_("descripción"), max_length=255)
    amount = models.DecimalField(_("monto"), max_digits=12, decimal_places=2)
    document = models.FileField(
        _("documento"), upload_to=expense_document_upload_path, blank=True, null=True,
        help_text=_("Factura, recibo u otro comprobante (opcional)."),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("registrado por"), related_name="expenses_recorded",
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    created_at = models.DateTimeField(_("creado"), auto_now_add=True)

    class Meta:
        verbose_name = _("gasto")
        verbose_name_plural = _("gastos del evento")
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.description} ({self.amount})"


class EventAdvance(models.Model):
    """A deposit/advance payment received from the client toward event
    expenses. There can be more than one — Event.advance_amount sums these."""

    event = models.ForeignKey(
        Event, verbose_name=_("evento"), related_name="advances", on_delete=models.CASCADE
    )
    date = models.DateField(_("fecha"))
    amount = models.DecimalField(_("monto"), max_digits=12, decimal_places=2)
    note = models.CharField(_("nota"), max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("registrado por"), related_name="advances_recorded",
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    created_at = models.DateTimeField(_("creado"), auto_now_add=True)

    class Meta:
        verbose_name = _("anticipo")
        verbose_name_plural = _("anticipos del evento")
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"Anticipo {self.amount} ({self.date})"


class Quotation(models.Model):
    """A client quote/estimate for an event, built as a dynamic list of items
    priced in Dominican pesos (DOP) with an automatic USD conversion — mirrors
    the planner's existing Excel workflow (fecha de realización / cliente /
    actividad / tasa de cambio + item table)."""

    event = models.ForeignKey(
        Event, verbose_name=_("evento"), related_name="quotations", on_delete=models.CASCADE
    )
    correlative = models.PositiveIntegerField(_("correlativo"), default=0)
    realization_date = models.DateField(_("fecha de realización"))
    client_name = models.CharField(_("cliente"), max_length=200)
    activity = models.CharField(_("actividad"), max_length=200)
    exchange_rate = models.DecimalField(_("tasa de cambio"), max_digits=10, decimal_places=4, default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("creada por"), related_name="quotations_created",
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    created_at = models.DateTimeField(_("creada"), auto_now_add=True)
    updated_at = models.DateTimeField(_("actualizada"), auto_now=True)

    class Meta:
        verbose_name = _("cotización")
        verbose_name_plural = _("cotizaciones")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Cotización {self.activity} — {self.client_name}"

    @property
    def total_dop(self):
        return sum((item.value_dop for item in self.items.all()), 0)

    @property
    def total_usd(self):
        if not self.exchange_rate:
            return 0
        return self.total_dop / self.exchange_rate


class QuotationItem(models.Model):
    quotation = models.ForeignKey(
        Quotation, verbose_name=_("cotización"), related_name="items", on_delete=models.CASCADE
    )
    vendor_name = models.CharField(_("proveedor"), max_length=150, blank=True)
    detail = models.CharField(_("detalle / item"), max_length=255)
    quantity = models.PositiveIntegerField(_("cantidad"), default=1)
    value_dop = models.DecimalField(_("valor (DOP)"), max_digits=12, decimal_places=2, default=0)
    order = models.PositiveIntegerField(_("orden"), default=0)

    class Meta:
        verbose_name = _("línea de cotización")
        verbose_name_plural = _("líneas de cotización")
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.detail} ({self.value_dop})"

    @property
    def value_usd(self):
        rate = self.quotation.exchange_rate
        return (self.value_dop / rate) if rate else 0


class Invoice(models.Model):
    """A client invoice for an event, printed over the planner's own invoice
    format: issuer header, bill-to block, job/payment terms, item table with
    total, and free-text payment instructions."""

    STATUS_ACTIVE = "vigente"
    STATUS_VOID = "anulada"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, _("Vigente")),
        (STATUS_VOID, _("Anulada")),
    ]

    event = models.ForeignKey(
        Event, verbose_name=_("evento"), related_name="invoices", on_delete=models.CASCADE
    )
    status = models.CharField(_("estado"), max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    voided_at = models.DateTimeField(_("anulada el"), null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("anulada por"), related_name="invoices_voided",
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    invoice_number = models.CharField(_("número de factura"), max_length=30)
    date = models.DateField(_("fecha"))
    issuer_name = models.CharField(_("nombre de quien factura"), max_length=200)
    issuer_contact = models.CharField(_("correo / teléfono"), max_length=200, blank=True)
    bill_to_name = models.CharField(_("facturar a"), max_length=200)
    bill_to_attn = models.CharField(_("atención de"), max_length=200, blank=True)
    bill_to_city = models.CharField(_("ciudad"), max_length=150, blank=True)
    bill_to_country = models.CharField(_("país"), max_length=150, blank=True)
    job_name = models.CharField(_("trabajo / evento"), max_length=200, blank=True)
    payment_terms = models.CharField(_("términos de pago"), max_length=200, blank=True)
    payment_instructions = models.TextField(_("instrucciones de pago"), blank=True)
    currency = models.CharField(_("moneda"), max_length=10, blank=True, default="USD")
    currency_symbol = models.CharField(_("signo de moneda"), max_length=5, blank=True, default="$")
    show_currency_symbol = models.BooleanField(
        _("mostrar signo de moneda"), default=False,
        help_text=_("Por defecto el signo no se muestra en los montos, solo si se activa aquí."),
    )
    payment_received = models.BooleanField(_("pago recibido"), default=False)
    payment_received_date = models.DateField(_("fecha de pago recibido"), null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("creada por"), related_name="invoices_created",
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    created_at = models.DateTimeField(_("creada"), auto_now_add=True)
    updated_at = models.DateTimeField(_("actualizada"), auto_now=True)

    class Meta:
        verbose_name = _("factura")
        verbose_name_plural = _("facturas")
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"Factura {self.invoice_number} — {self.bill_to_name}"

    @property
    def total(self):
        return sum((item.amount for item in self.items.all()), 0)


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(
        Invoice, verbose_name=_("factura"), related_name="items", on_delete=models.CASCADE
    )
    description = models.CharField(_("descripción"), max_length=255)
    amount = models.DecimalField(_("monto"), max_digits=12, decimal_places=2, default=0)
    order = models.PositiveIntegerField(_("orden"), default=0)

    class Meta:
        verbose_name = _("línea de factura")
        verbose_name_plural = _("líneas de factura")
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.description} ({self.amount})"
