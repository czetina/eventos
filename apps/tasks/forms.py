from django import forms
from django.utils.translation import gettext_lazy as _

from apps.accounts.forms import BootstrapFormMixin
from apps.events.models import EventTeamMember

from .models import Task, TaskEvidence


class TaskForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            "title", "description", "category", "assigned_to", "supervisor",
            "due_date", "due_time", "requires_photo", "requires_document",
        ]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
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
                    event=event, role_in_event__in=[EventTeamMember.ROLE_SUPERVISOR, EventTeamMember.ROLE_PLANNER]
                ).values_list("user_id", flat=True)
            )
        self.fields["supervisor"].required = False
        self._apply_bootstrap()


class TaskEvidenceForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = TaskEvidence
        fields = ["file", "comment"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["comment"].required = False
        self._apply_bootstrap()
