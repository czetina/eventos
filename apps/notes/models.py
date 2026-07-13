from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.events.models import Event


class Note(models.Model):
    """A free-form note attached to an event (reminders, agreements, ideas)."""

    event = models.ForeignKey(
        Event, verbose_name=_("evento"), related_name="notes", on_delete=models.CASCADE
    )
    content = models.TextField(_("contenido"))
    pinned = models.BooleanField(_("fijada"), default=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("autor"),
        related_name="notes_written",
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(_("creada"), auto_now_add=True)

    class Meta:
        verbose_name = _("nota")
        verbose_name_plural = _("notas")
        ordering = ["-pinned", "-created_at"]

    def __str__(self):
        return self.content[:60]


def event_file_upload_path(instance, filename):
    return f"archivos/evento_{instance.event_id}/{filename}"


class EventFile(models.Model):
    """A general document/file attached to an event (contracts, layouts, permits, etc.)."""

    event = models.ForeignKey(
        Event, verbose_name=_("evento"), related_name="files", on_delete=models.CASCADE
    )
    file = models.FileField(_("archivo"), upload_to=event_file_upload_path)
    title = models.CharField(_("título"), max_length=150, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("subido por"),
        related_name="event_files_uploaded",
        on_delete=models.SET_NULL,
        null=True,
    )
    uploaded_at = models.DateTimeField(_("subido el"), auto_now_add=True)

    class Meta:
        verbose_name = _("archivo del evento")
        verbose_name_plural = _("archivos del evento")
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title or self.file.name
