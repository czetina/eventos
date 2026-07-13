from django import forms
from django.utils.translation import gettext_lazy as _

from apps.accounts.forms import BootstrapFormMixin
from apps.accounts.models import User

from .models import Event, EventSession, EventTeamMember


class EventForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "name", "event_type", "client_name", "client_phone", "client_email",
            "country", "city", "venue_name", "venue_address",
            "event_date", "start_time", "end_time", "status", "description", "planner",
        ]
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields["planner"].queryset = User.objects.filter(
                company=company, role__in=[User.ROLE_PLANNER, User.ROLE_COMPANY_ADMIN]
            )
        self.fields["planner"].required = False
        self._apply_bootstrap()


class EventSessionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = EventSession
        fields = ["title", "venue_name", "address", "start_time", "end_time", "notes", "order"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class EventTeamMemberForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = EventTeamMember
        fields = ["user", "role_in_event", "area", "reports_to"]

    def __init__(self, *args, company=None, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields["user"].queryset = User.objects.filter(company=company, is_active=True)
        if event:
            self.fields["reports_to"].queryset = EventTeamMember.objects.filter(event=event)
        self.fields["reports_to"].required = False
        self._apply_bootstrap()
