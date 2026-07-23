from django import forms
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.forms import BootstrapFormMixin
from apps.accounts.models import Role
from apps.events.models import EventTeamMember
from apps.vendors.models import Vendor

from .models import Task, TaskEvidence, TaskStatusHistory


class TaskForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            "title", "description", "category", "assigned_to", "vendor", "external_assignee_name",
            "supervisor", "itinerary_session", "is_guion", "due_date", "due_time",
            "requires_photo", "requires_video", "requires_document",
        ]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "due_time": forms.TimeInput(attrs={"type": "time"}),
            "description": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        if event:
            member_user_ids = EventTeamMember.objects.filter(event=event).values_list("user_id", flat=True)
            self.fields["assigned_to"].queryset = self.fields["assigned_to"].queryset.model.objects.filter(
                pk__in=member_user_ids
            )
            self.fields["supervisor"].queryset = self.fields["supervisor"].queryset.model.objects.filter(
                pk__in=EventTeamMember.objects.filter(
                    event=event, role__base_level__in=[Role.LEVEL_SUPERVISOR, Role.LEVEL_PLANNER]
                ).values_list("user_id", flat=True)
            )
            vendor_filter = models.Q(is_active=True)
            if self.instance.pk and self.instance.vendor_id:
                vendor_filter |= models.Q(pk=self.instance.vendor_id)
            self.fields["vendor"].queryset = Vendor.objects.filter(vendor_filter, company=event.company)
            self.fields["itinerary_session"].queryset = event.sessions.all()
        self.fields["assigned_to"].required = False
        self.fields["vendor"].required = False
        self.fields["supervisor"].required = False
        self.fields["itinerary_session"].required = False
        self._apply_bootstrap()

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("assigned_to") and not cleaned.get("vendor") and not cleaned.get("external_assignee_name"):
            raise forms.ValidationError(
                _("Indica un encargado del sistema, un proveedor o un responsable externo.")
            )
        return cleaned


class TaskImportForm(BootstrapFormMixin, forms.Form):
    SOURCE_TASK_PER_PERSON = "task_per_person"
    SOURCE_GUION_COMPLETO = "guion_completo"
    SOURCE_GUION_FINAL = "guion_final"
    SOURCE_CHOICES = [
        (SOURCE_TASK_PER_PERSON, _("Task por persona (responsible / task / hecho)")),
        (SOURCE_GUION_COMPLETO, _("Guion completo (fecha / hora / responsable / ubicación / descripción)")),
        (SOURCE_GUION_FINAL, _("Guion final (fecha / hora / responsable(s) / actividad / proveedor / ubicación / tarea)")),
    ]

    source_type = forms.ChoiceField(label=_("Tipo de archivo"), choices=SOURCE_CHOICES)
    file = forms.FileField(label=_("Archivo Excel (.xlsx)"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith((".xlsx", ".xlsm")):
            raise forms.ValidationError(_("Sube un archivo Excel (.xlsx)."))
        return f


class TaskStatusChangeForm(BootstrapFormMixin, forms.Form):
    status = forms.ChoiceField(label=_("Nuevo estado"), choices=Task.STATUS_CHOICES)
    changed_at = forms.DateTimeField(
        label=_("Fecha y hora en que ocurrió"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    note = forms.CharField(
        label=_("Motivo / explicación"), required=False, widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class TaskStatusHistoryEditForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TaskStatusHistory
        fields = ["status", "changed_at", "note"]
        widgets = {
            "changed_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "note": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["changed_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self._apply_bootstrap()


class TaskEvidenceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TaskEvidence
        fields = ["file", "comment"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["comment"].required = False
        self._apply_bootstrap()
