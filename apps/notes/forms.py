from django import forms

from apps.accounts.forms import BootstrapFormMixin

from .models import EventFile, Note


class NoteForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Note
        fields = ["content", "pinned"]
        widgets = {"content": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class EventFileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = EventFile
        fields = ["title", "file"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()
