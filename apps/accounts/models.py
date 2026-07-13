from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField


class Company(models.Model):
    """Tenant: a wedding/event planning agency using the platform."""

    name = models.CharField(_("nombre"), max_length=150)
    country = CountryField(_("país"), blank_label=_("(selecciona un país)"))
    city = models.CharField(_("ciudad"), max_length=120, blank=True)
    phone = models.CharField(_("teléfono"), max_length=40, blank=True)
    email = models.EmailField(_("correo de contacto"), blank=True)
    is_active = models.BooleanField(_("activa"), default=True)
    created_at = models.DateTimeField(_("creada"), auto_now_add=True)

    class Meta:
        verbose_name = _("empresa")
        verbose_name_plural = _("empresas")
        ordering = ["name"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    """Custom user with a role inside a Company (tenant)."""

    ROLE_COMPANY_ADMIN = "company_admin"
    ROLE_PLANNER = "planner"
    ROLE_SUPERVISOR = "supervisor"
    ROLE_ENCARGADO = "encargado"

    ROLE_CHOICES = [
        (ROLE_COMPANY_ADMIN, _("Administrador de empresa")),
        (ROLE_PLANNER, _("Planificador")),
        (ROLE_SUPERVISOR, _("Supervisor")),
        (ROLE_ENCARGADO, _("Encargado")),
    ]

    # Higher number = more authority. Used for permission checks.
    ROLE_LEVELS = {
        ROLE_COMPANY_ADMIN: 4,
        ROLE_PLANNER: 3,
        ROLE_SUPERVISOR: 2,
        ROLE_ENCARGADO: 1,
    }

    LANGUAGE_CHOICES = [
        ("es", "Español"),
        ("en", "English"),
    ]

    company = models.ForeignKey(
        Company,
        verbose_name=_("empresa"),
        related_name="users",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    role = models.CharField(
        _("rol"), max_length=20, choices=ROLE_CHOICES, default=ROLE_ENCARGADO
    )
    phone = models.CharField(_("teléfono"), max_length=40, blank=True)
    preferred_language = models.CharField(
        _("idioma preferido"), max_length=5, choices=LANGUAGE_CHOICES, default="es"
    )
    created_at = models.DateTimeField(_("creado"), auto_now_add=True)

    class Meta:
        verbose_name = _("usuario")
        verbose_name_plural = _("usuarios")

    def __str__(self):
        full_name = self.get_full_name()
        return full_name or self.username

    @property
    def role_level(self):
        return self.ROLE_LEVELS.get(self.role, 0)

    def has_role_at_least(self, role):
        return self.role_level >= self.ROLE_LEVELS.get(role, 0)

    @property
    def is_company_admin(self):
        return self.role == self.ROLE_COMPANY_ADMIN

    @property
    def is_planner(self):
        return self.role == self.ROLE_PLANNER

    @property
    def is_supervisor(self):
        return self.role == self.ROLE_SUPERVISOR

    @property
    def is_encargado(self):
        return self.role == self.ROLE_ENCARGADO

    @property
    def can_manage_events(self):
        """Company admins and planners may create/edit events."""
        return self.is_superuser or self.role in (
            self.ROLE_COMPANY_ADMIN,
            self.ROLE_PLANNER,
        )
