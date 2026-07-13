from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _

from .models import Company, User

BOOTSTRAP_WIDGETS = (forms.TextInput, forms.EmailInput, forms.PasswordInput, forms.Select,
                     forms.Textarea, forms.NumberInput, forms.DateInput, forms.TimeInput)


class BootstrapFormMixin:
    """Adds the 'form-control'/'form-select' Bootstrap 5 classes to every field."""

    def _apply_bootstrap(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            elif isinstance(widget, BOOTSTRAP_WIDGETS):
                widget.attrs.setdefault("class", "form-control")


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class CompanyRegistrationForm(BootstrapFormMixin, forms.Form):
    """Registers a new agency (tenant) together with its first admin user."""

    company_name = forms.CharField(label=_("Nombre de la empresa"), max_length=150)
    country = forms.CharField(label=_("País"), max_length=2, widget=forms.Select())
    city = forms.CharField(label=_("Ciudad"), max_length=120, required=False)

    first_name = forms.CharField(label=_("Nombre"), max_length=150)
    last_name = forms.CharField(label=_("Apellido"), max_length=150)
    email = forms.EmailField(label=_("Correo"))
    username = forms.CharField(label=_("Usuario"), max_length=150)
    password1 = forms.CharField(label=_("Contraseña"), widget=forms.PasswordInput)
    password2 = forms.CharField(label=_("Confirmar contraseña"), widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["country"].widget = forms.Select(choices=Company._meta.get_field("country").choices)
        self._apply_bootstrap()

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError(_("Ese nombre de usuario ya está en uso."))
        return username

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", _("Las contraseñas no coinciden."))
        if p1 and len(p1) < 8:
            self.add_error("password1", _("La contraseña debe tener al menos 8 caracteres."))
        return cleaned

    def save(self):
        data = self.cleaned_data
        company = Company.objects.create(
            name=data["company_name"], country=data["country"], city=data["city"]
        )
        user = User.objects.create_user(
            username=data["username"],
            email=data["email"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            password=data["password1"],
            company=company,
            role=User.ROLE_COMPANY_ADMIN,
        )
        return user


class TeamMemberForm(BootstrapFormMixin, forms.ModelForm):
    """Used by company_admin/planner to invite a new team member (supervisor/encargado/planner)."""

    password1 = forms.CharField(label=_("Contraseña"), widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "email", "phone", "role", "preferred_language"]

    def __init__(self, *args, requesting_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        allowed_roles = User.ROLE_CHOICES
        if requesting_user and not requesting_user.is_company_admin and not requesting_user.is_superuser:
            allowed_roles = [c for c in User.ROLE_CHOICES if c[0] != User.ROLE_COMPANY_ADMIN]
        self.fields["role"].choices = allowed_roles
        self._apply_bootstrap()

    def clean_username(self):
        username = self.cleaned_data["username"]
        qs = User.objects.filter(username=username)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(_("Ese nombre de usuario ya está en uso."))
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class TeamMemberEditForm(BootstrapFormMixin, forms.ModelForm):
    """Edits an existing team member without touching the password."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "role", "preferred_language", "is_active"]

    def __init__(self, *args, requesting_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        allowed_roles = User.ROLE_CHOICES
        if requesting_user and not requesting_user.is_company_admin and not requesting_user.is_superuser:
            allowed_roles = [c for c in User.ROLE_CHOICES if c[0] != User.ROLE_COMPANY_ADMIN]
        self.fields["role"].choices = allowed_roles
        self._apply_bootstrap()


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "preferred_language"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()
