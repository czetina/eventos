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


class EventSession(models.Model):
    """A time block within an event's itinerary (ceremony, cocktail, reception...),
    each with its own date, potentially at a different venue. Supports multi-day
    events (rehearsal, montaje, the event day itself, desmontaje) as well as
    multiple happenings on the same day."""

    SECTION_CEREMONIA = "ceremonia"
    SECTION_RECEPCION = "recepcion"
    SECTION_MONTAJE = "montaje"
    SECTION_DESMONTAJE = "desmontaje"
    SECTION_OTRO = "otro"

    SECTION_CHOICES = [
        (SECTION_CEREMONIA, _("Ceremonia")),
        (SECTION_RECEPCION, _("Recepción")),
        (SECTION_MONTAJE, _("Montaje")),
        (SECTION_DESMONTAJE, _("Desmontaje")),
        (SECTION_OTRO, _("Otro")),
    ]

    event = models.ForeignKey(
        Event, verbose_name=_("evento"), related_name="sessions", on_delete=models.CASCADE
    )
    section = models.CharField(
        _("sección"), max_length=20, choices=SECTION_CHOICES, default=SECTION_OTRO,
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


class ProcessionalEntry(models.Model):
    """One step of the church processional order — who enters (or exits) on
    each side of the aisle (plus an optional center position for someone who
    walks alone down the middle), in walking order, feeding the auto-generated
    top-down diagram used for the ceremony rehearsal.

    The altar is always drawn at the top of the diagram and the church doors
    at the bottom, matching how a planner reads a floor plan. For the
    'entrada' phase, order=1 is shown right at the altar (top) and the last
    order is shown at the church entrance (bottom); for 'salida' it's the
    reverse (order=1 at the exit/bottom, last order at the altar/top), so the
    two phases are rendered in opposite row order."""

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
