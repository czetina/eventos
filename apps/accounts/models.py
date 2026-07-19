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


class Role(models.Model):
    """A company-defined role (e.g. 'Novia', 'Asistente', 'Representante de Venue').

    Each custom role inherits the permissions of one of the four fixed technical
    tiers below, so the app's permission logic never has to guess what a role can
    do — only what to call it and how to describe it to the team.
    """

    LEVEL_COMPANY_ADMIN = "company_admin"
    LEVEL_PLANNER = "planner"
    LEVEL_SUPERVISOR = "supervisor"
    LEVEL_ENCARGADO = "encargado"

    LEVEL_CHOICES = [
        (LEVEL_COMPANY_ADMIN, _("Administrador de empresa (gestiona toda la empresa)")),
        (LEVEL_PLANNER, _("Planificador (crea y gestiona eventos)")),
        (LEVEL_SUPERVISOR, _("Supervisor (coordina un equipo o área)")),
        (LEVEL_ENCARGADO, _("Encargado (ejecuta tareas asignadas)")),
    ]

    # Higher number = more authority. Used for permission checks.
    LEVEL_RANKS = {
        LEVEL_COMPANY_ADMIN: 4,
        LEVEL_PLANNER: 3,
        LEVEL_SUPERVISOR: 2,
        LEVEL_ENCARGADO: 1,
    }

    company = models.ForeignKey(
        Company, verbose_name=_("empresa"), related_name="roles", on_delete=models.CASCADE
    )
    name = models.CharField(_("nombre del rol"), max_length=100)
    description = models.TextField(
        _("qué hace este rol"), blank=True,
        help_text=_("Ej. 'Coordina montaje y desmontaje', 'Contacto de la pareja para aprobaciones'"),
    )
    base_level = models.CharField(_("nivel de permisos"), max_length=20, choices=LEVEL_CHOICES)
    is_default = models.BooleanField(
        _("rol por defecto"), default=False,
        help_text=_("Roles creados automáticamente con la empresa; no se pueden eliminar."),
    )
    created_at = models.DateTimeField(_("creado"), auto_now_add=True)

    class Meta:
        verbose_name = _("rol")
        verbose_name_plural = _("roles")
        unique_together = [("company", "name")]
        ordering = ["-is_default", "name"]

    def __str__(self):
        return self.name

    @property
    def level_rank(self):
        return self.LEVEL_RANKS.get(self.base_level, 0)


DEFAULT_ROLES = [
    (Role.LEVEL_COMPANY_ADMIN, "Administrador de empresa"),
    (Role.LEVEL_PLANNER, "Planificador"),
    (Role.LEVEL_SUPERVISOR, "Supervisor"),
    (Role.LEVEL_ENCARGADO, "Encargado"),
]


def create_default_roles(company):
    """Called when a new Company is registered so it always starts with the four
    base roles available; more can be added afterwards via role management."""
    roles = {}
    for base_level, name in DEFAULT_ROLES:
        role, _created = Role.objects.get_or_create(
            company=company, name=name, defaults={"base_level": base_level, "is_default": True}
        )
        roles[base_level] = role
    return roles


class User(AbstractUser):
    """Custom user with a company-defined Role inside a Company (tenant)."""

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
    role = models.ForeignKey(
        Role,
        verbose_name=_("rol"),
        related_name="users",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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
        return self.role.level_rank if self.role else 0

    def has_role_at_least(self, base_level):
        return self.role_level >= Role.LEVEL_RANKS.get(base_level, 0)

    @property
    def is_company_admin(self):
        return bool(self.role and self.role.base_level == Role.LEVEL_COMPANY_ADMIN)

    @property
    def is_planner(self):
        return bool(self.role and self.role.base_level == Role.LEVEL_PLANNER)

    @property
    def is_supervisor(self):
        return bool(self.role and self.role.base_level == Role.LEVEL_SUPERVISOR)

    @property
    def is_encargado(self):
        return bool(self.role and self.role.base_level == Role.LEVEL_ENCARGADO)

    @property
    def can_manage_events(self):
        """Company admins and planners may create/edit events."""
        return self.is_superuser or (
            self.role and self.role.base_level in (Role.LEVEL_COMPANY_ADMIN, Role.LEVEL_PLANNER)
        )
