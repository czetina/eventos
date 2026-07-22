from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import Role
from apps.events.models import Event, EventSession
from apps.vendors.models import Vendor


def evidence_upload_path(instance, filename):
    event_id = instance.task.event_id
    return f"evidencias/evento_{event_id}/tarea_{instance.task_id}/{filename}"


class Task(models.Model):
    """A checklist item assigned to a responsible person (encargado) for an event.

    Example: 'Juan revisa instalación de mesas' -> requires photo evidence + timestamp.
    'Recepción de licor' -> requires uploading the delivery document + timestamp.
    """

    STATUS_PENDING = "pendiente"
    STATUS_IN_PROGRESS = "en_progreso"
    STATUS_DONE = "completada"
    STATUS_BLOCKED = "con_problema"

    STATUS_CHOICES = [
        (STATUS_PENDING, _("Pendiente")),
        (STATUS_IN_PROGRESS, _("En progreso")),
        (STATUS_DONE, _("Completada")),
        (STATUS_BLOCKED, _("Con problema")),
    ]

    event = models.ForeignKey(
        Event, verbose_name=_("evento"), related_name="tasks", on_delete=models.CASCADE
    )
    title = models.CharField(_("tarea"), max_length=200)
    description = models.TextField(_("descripción"), blank=True)
    category = models.CharField(
        _("categoría"), max_length=100, blank=True,
        help_text=_("Ej. Montaje, Logística, Decoración, Insumos"),
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("encargado"),
        related_name="tasks_assigned",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    vendor = models.ForeignKey(
        Vendor,
        verbose_name=_("proveedor responsable"),
        related_name="tasks",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text=_("Proveedor registrado responsable de esta tarea, en vez de un usuario del sistema"),
    )
    external_assignee_name = models.CharField(
        _("responsable externo"), max_length=150, blank=True,
        help_text=_("Nombre de un contacto (proveedor o cliente) que no tiene usuario ni ficha en el sistema"),
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("supervisor"),
        related_name="tasks_supervised",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    itinerary_session = models.ForeignKey(
        EventSession,
        verbose_name=_("momento del itinerario"),
        related_name="tasks",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text=_("Vincula esta tarea a un momento específico del itinerario (opcional)"),
    )

    due_date = models.DateField(_("fecha límite"), null=True, blank=True)
    due_time = models.TimeField(_("hora límite"), null=True, blank=True)

    requires_photo = models.BooleanField(_("requiere foto"), default=False)
    requires_video = models.BooleanField(_("requiere video"), default=False)
    requires_document = models.BooleanField(_("requiere documento"), default=False)

    status = models.CharField(
        _("estado"), max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("creado por"),
        related_name="tasks_created",
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(_("creado"), auto_now_add=True)
    updated_at = models.DateTimeField(_("actualizado"), auto_now=True)

    completed_at = models.DateTimeField(
        _("completada el"), null=True, blank=True,
        help_text=_("Fecha y hora real en que se hizo la tarea; por defecto es ahora, pero se puede ajustar."),
    )
    completion_recorded_at = models.DateTimeField(
        _("registrada en el sistema el"), null=True, blank=True,
        help_text=_("Momento exacto en que quedó guardado en el sistema (no editable)."),
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("completada por"),
        related_name="tasks_completed",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("tarea")
        verbose_name_plural = _("tareas")
        ordering = ["due_date", "due_time", "id"]

    def __str__(self):
        return f"{self.title} ({self.event})"

    def get_absolute_url(self):
        return reverse("tasks:detail", args=[self.pk])

    @property
    def requires_evidence(self):
        return self.requires_photo or self.requires_video or self.requires_document

    @property
    def responsible_display(self):
        if self.assigned_to:
            return str(self.assigned_to)
        if self.vendor:
            return str(self.vendor.name)
        return self.external_assignee_name or _("Sin asignar")

    @property
    def is_overdue(self):
        if self.status == self.STATUS_DONE or not self.due_date:
            return False
        today = timezone.localdate()
        if self.due_date < today:
            return True
        if self.due_date == today and self.due_time:
            return timezone.localtime().time() > self.due_time
        return False

    @property
    def days_overdue(self):
        if not self.is_overdue:
            return 0
        return (timezone.localdate() - self.due_date).days

    def can_be_completed_by(self, user):
        return user == self.assigned_to or user.has_role_at_least(Role.LEVEL_SUPERVISOR)

    def mark_completed(self, user, completed_at=None):
        now = timezone.now()
        self.status = self.STATUS_DONE
        self.completed_at = completed_at or now
        self.completion_recorded_at = now
        self.completed_by = user
        self.save(update_fields=[
            "status", "completed_at", "completion_recorded_at", "completed_by", "updated_at",
        ])
        self.record_status_change(user, changed_at=self.completed_at)

    def record_status_change(self, user, note="", changed_at=None):
        """Appends an entry to this task's status history — call whenever `status`
        changes (creation, manual edit, completion, bulk actions, or an explicit
        'Cambiar estado' action that can backdate the change and explain why)."""
        TaskStatusHistory.objects.create(
            task=self, status=self.status, changed_by=user, note=note,
            changed_at=changed_at or timezone.now(),
        )

    def change_status(self, user, status, changed_at=None, note=""):
        """Explicit status change with a specific date and an explanation — used by
        the 'Cambiar estado' action, including reverting a mistaken 'Completada'."""
        changed_at = changed_at or timezone.now()
        self.status = status
        if status == self.STATUS_DONE:
            self.completed_at = changed_at
            self.completion_recorded_at = timezone.now()
            self.completed_by = user
        else:
            self.completed_at = None
            self.completion_recorded_at = None
            self.completed_by = None
        self.save(update_fields=[
            "status", "completed_at", "completion_recorded_at", "completed_by", "updated_at",
        ])
        self.record_status_change(user, note=note, changed_at=changed_at)

    def recompute_status_from_history(self):
        """Keeps `status` (and the completion fields) in sync with whatever is now
        the most recent TaskStatusHistory row — called after editing or deleting a
        history entry, since 'the last status stays as the current status'."""
        latest = self.status_history.order_by("-changed_at", "-pk").first()
        if latest is None:
            self.status = self.STATUS_PENDING
            self.completed_at = None
            self.completion_recorded_at = None
            self.completed_by = None
        else:
            self.status = latest.status
            if latest.status == self.STATUS_DONE:
                self.completed_at = latest.changed_at
                self.completed_by = latest.changed_by
                self.completion_recorded_at = self.completion_recorded_at or latest.changed_at
            else:
                self.completed_at = None
                self.completion_recorded_at = None
                self.completed_by = None
        self.save(update_fields=[
            "status", "completed_at", "completion_recorded_at", "completed_by", "updated_at",
        ])


class TaskEvidence(models.Model):
    """A photo or document uploaded as proof that a task was performed."""

    task = models.ForeignKey(
        Task, verbose_name=_("tarea"), related_name="evidences", on_delete=models.CASCADE
    )
    file = models.FileField(_("archivo"), upload_to=evidence_upload_path)
    comment = models.CharField(_("comentario"), max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("subido por"),
        related_name="evidences_uploaded",
        on_delete=models.SET_NULL,
        null=True,
    )
    uploaded_at = models.DateTimeField(_("subido el"), auto_now_add=True)

    class Meta:
        verbose_name = _("evidencia")
        verbose_name_plural = _("evidencias")
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"Evidencia de {self.task} ({self.uploaded_at:%Y-%m-%d %H:%M})"

    @property
    def is_image(self):
        name = self.file.name.lower()
        return name.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))

    @property
    def is_video(self):
        name = self.file.name.lower()
        return name.endswith((".mp4", ".mov", ".avi", ".webm", ".m4v"))


class TaskStatusHistory(models.Model):
    """Audit trail: one row per status change, so a task's timeline (and event-wide
    reports) can show exactly when it moved from pending to in-progress to done."""

    task = models.ForeignKey(
        Task, verbose_name=_("tarea"), related_name="status_history", on_delete=models.CASCADE
    )
    status = models.CharField(_("estado"), max_length=20, choices=Task.STATUS_CHOICES)
    changed_at = models.DateTimeField(_("fecha del cambio"), default=timezone.now)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("cambiado por"),
        related_name="task_status_changes",
        on_delete=models.SET_NULL,
        null=True,
    )
    note = models.CharField(_("nota"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("historial de estado")
        verbose_name_plural = _("historial de estados")
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.task} → {self.get_status_display()} ({self.changed_at:%Y-%m-%d %H:%M})"
