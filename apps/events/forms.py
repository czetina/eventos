from django import forms
from django.utils.translation import gettext_lazy as _

from apps.accounts.forms import BootstrapFormMixin
from apps.accounts.models import Role, User

from .models import (
    Event, EventSession, EventTeamMember, MealCount, ProcessionalEntry, WeddingPartyMember, WeddingPartyListType,
)


class EventForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            "name", "event_type", "client_name", "client_phone", "client_email",
            "country", "city", "venue_name", "venue_address",
            "civil_ceremony_venue", "religious_ceremony_venue", "cocktail_venue",
            "event_date", "start_time", "end_time", "status", "description", "planner",
        ]
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields["planner"].queryset = User.objects.filter(
                company=company, role__base_level__in=[Role.LEVEL_PLANNER, Role.LEVEL_COMPANY_ADMIN]
            )
        self.fields["planner"].required = False
        self._apply_bootstrap()


class EventSessionForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = EventSession
        fields = ["section", "title", "venue_name", "address", "date", "start_time", "end_time", "notes", "order"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class SessionImportForm(BootstrapFormMixin, forms.Form):
    file = forms.FileField(label=_("Archivo Excel (.xlsx) — minuto a minuto"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith((".xlsx", ".xlsm")):
            raise forms.ValidationError(_("Sube un archivo Excel (.xlsx)."))
        return f


class EventTeamMemberForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = EventTeamMember
        fields = ["user", "role", "area", "reports_to"]

    def __init__(self, *args, company=None, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields["user"].queryset = User.objects.filter(company=company, is_active=True)
            self.fields["role"].queryset = Role.objects.filter(company=company)
        if event:
            self.fields["reports_to"].queryset = EventTeamMember.objects.filter(event=event)
        self.fields["reports_to"].required = False
        self._apply_bootstrap()


class WeddingPartyListTypeForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = WeddingPartyListType
        fields = ["name", "order"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class WeddingPartyMemberForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = WeddingPartyMember
        fields = ["list_type", "name", "role_description", "quantity", "order", "table_number", "notes"]

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields["list_type"].queryset = WeddingPartyListType.objects.filter(company=company)
        self._apply_bootstrap()


class ProcessionalEntryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ProcessionalEntry
        fields = [
            "phase", "order", "left_name", "center_name", "right_name",
            "detail", "detail_visible_public", "music",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class MealCountForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = MealCount
        fields = ["group", "target_name", "meal_label", "count", "amount", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()
