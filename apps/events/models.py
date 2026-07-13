from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField

from apps.accounts.models import Company


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
    each potentially at a different venue. Supports multiple happenings in a single day."""

    event = models.ForeignKey(
        Event, verbose_name=_("evento"), related_name="sessions", on_delete=models.CASCADE
    )
    title = models.CharField(_("actividad"), max_length=150)
    venue_name = models.CharField(_("lugar"), max_length=200, blank=True)
    address = models.CharField(_("dirección"), max_length=255, blank=True)
    start_time = models.TimeField(_("hora de inicio"))
    end_time = models.TimeField(_("hora de fin"), null=True, blank=True)
    notes = models.TextField(_("notas"), blank=True)
    order = models.PositiveIntegerField(_("orden"), default=0)

    class Meta:
        verbose_name = _("actividad del itinerario")
        verbose_name_plural = _("itinerario")
        ordering = ["order", "start_time"]

    def __str__(self):
        return f"{self.title} - {self.start_time}"


class EventTeamMember(models.Model):
    """Assigns a user to an event with a role and an optional supervisor,
    modeling the hierarchy (supervisor / encargado) for that specific event."""

    ROLE_PLANNER = "planner"
    ROLE_SUPERVISOR = "supervisor"
    ROLE_ENCARGADO = "encargado"

    EVENT_ROLE_CHOICES = [
        (ROLE_PLANNER, _("Planificador")),
        (ROLE_SUPERVISOR, _("Supervisor")),
        (ROLE_ENCARGADO, _("Encargado")),
    ]

    event = models.ForeignKey(
        Event, verbose_name=_("evento"), related_name="team_members", on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("usuario"),
        related_name="event_memberships",
        on_delete=models.CASCADE,
    )
    role_in_event = models.CharField(
        _("rol en el evento"), max_length=20, choices=EVENT_ROLE_CHOICES, default=ROLE_ENCARGADO
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
        ordering = ["role_in_event", "area"]

    def __str__(self):
        return f"{self.user} - {self.get_role_in_event_display()} ({self.event})"
