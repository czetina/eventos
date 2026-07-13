from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.events.models import Event


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
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("supervisor"),
        related_name="tasks_supervised",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    due_date = models.DateField(_("fecha límite"), null=True, blank=True)
    due_time = models.TimeField(_("hora límite"), null=True, blank=True)

    requires_photo = models.BooleanField(_("requiere foto"), default=False)
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

    completed_at = models.DateTimeField(_("completada el"), null=True, blank=True)
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
        return self.requires_photo or self.requires_document

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

    def can_be_completed_by(self, user):
        return user == self.assigned_to or user.has_role_at_least(user.ROLE_SUPERVISOR)

    def mark_completed(self, user):
        self.status = self.STATUS_DONE
        self.completed_at = timezone.now()
        self.completed_by = user
        self.save(update_fields=["status", "completed_at", "completed_by", "updated_at"])


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
