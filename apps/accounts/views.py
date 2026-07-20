from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from .forms import (
    CompanyRegistrationForm, LoginForm, ProfileForm, RoleForm,
    TeamMemberEditForm, TeamMemberForm, TeamMemberPasswordForm,
)
from .models import Role, User


def apply_user_language(request, response, language):
    """Activates the user's preferred language for this response and remembers it via cookie."""
    translation.activate(language)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME, language,
        max_age=settings.LANGUAGE_COOKIE_AGE, path=settings.LANGUAGE_COOKIE_PATH,
        domain=settings.LANGUAGE_COOKIE_DOMAIN, secure=settings.LANGUAGE_COOKIE_SECURE,
        httponly=settings.LANGUAGE_COOKIE_HTTPONLY, samesite=settings.LANGUAGE_COOKIE_SAMESITE,
    )
    return response


class CompanyLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        return apply_user_language(self.request, response, self.request.user.preferred_language)


class CompanyLogoutView(LogoutView):
    pass


def register_company(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    if request.method == "POST":
        form = CompanyRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, _("¡Empresa registrada! Ya puedes crear tu primer evento."))
            return redirect("core:dashboard")
    else:
        form = CompanyRegistrationForm()
    return render(request, "accounts/register_company.html", {"form": form})


def _can_manage_team(user):
    return user.can_manage_events


@login_required
def team_list(request):
    if not request.user.company:
        return render(request, "accounts/team_list.html", {"members": []})
    members = User.objects.filter(company=request.user.company).select_related("role").order_by(
        "role__name", "first_name"
    )
    return render(request, "accounts/team_list.html", {
        "members": members,
        "can_manage": _can_manage_team(request.user),
    })


@login_required
def team_create(request):
    if not _can_manage_team(request.user):
        raise PermissionDenied(_("No tienes permiso para agregar miembros al equipo."))
    if request.method == "POST":
        form = TeamMemberForm(request.POST, requesting_user=request.user)
        if form.is_valid():
            user = form.save(commit=False)
            user.company = request.user.company
            user.save()
            messages.success(request, _("Miembro del equipo creado correctamente."))
            return redirect("accounts:team_list")
    else:
        form = TeamMemberForm(requesting_user=request.user)
    return render(request, "accounts/team_form.html", {"form": form, "is_new": True})


@login_required
def team_edit(request, pk):
    if not _can_manage_team(request.user):
        raise PermissionDenied(_("No tienes permiso para editar miembros del equipo."))
    member = get_object_or_404(User, pk=pk, company=request.user.company)
    if request.method == "POST":
        form = TeamMemberEditForm(request.POST, instance=member, requesting_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _("Datos actualizados correctamente."))
            return redirect("accounts:team_list")
    else:
        form = TeamMemberEditForm(instance=member, requesting_user=request.user)
    return render(request, "accounts/team_form.html", {"form": form, "is_new": False, "member": member})


@login_required
def team_change_password(request, pk):
    if not _can_manage_team(request.user):
        raise PermissionDenied(_("No tienes permiso para cambiar contraseñas del equipo."))
    member = get_object_or_404(User, pk=pk, company=request.user.company)
    if request.method == "POST":
        form = TeamMemberPasswordForm(request.POST)
        if form.is_valid():
            member.set_password(form.cleaned_data["password1"])
            member.save()
            messages.success(request, _("Contraseña actualizada."))
            return redirect("accounts:team_list")
    else:
        form = TeamMemberPasswordForm()
    return render(request, "accounts/team_password_form.html", {"form": form, "member": member})


@login_required
def team_delete(request, pk):
    if not _can_manage_team(request.user):
        raise PermissionDenied(_("No tienes permiso para eliminar miembros del equipo."))
    member = get_object_or_404(User, pk=pk, company=request.user.company)
    if request.method == "POST":
        if member.pk == request.user.pk:
            messages.error(request, _("No puedes eliminar tu propia cuenta."))
        elif member.tasks_assigned.exists() or member.event_memberships.exists():
            messages.error(request, _(
                "No se puede eliminar: tiene tareas o eventos asignados. Márcalo como inactivo en su lugar."
            ))
        else:
            member.delete()
            messages.success(request, _("Miembro del equipo eliminado."))
    return redirect("accounts:team_list")


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _("Perfil actualizado."))
            return apply_user_language(request, redirect("accounts:profile"), request.user.preferred_language)
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile.html", {"form": form})


@login_required
def role_list(request):
    if not request.user.is_company_admin and not request.user.is_superuser:
        raise PermissionDenied(_("Solo un administrador de empresa puede gestionar roles."))
    roles = Role.objects.filter(company=request.user.company).annotate(
        member_count=models.Count("users")
    )
    return render(request, "accounts/role_list.html", {"roles": roles})


@login_required
def role_create(request):
    if not request.user.is_company_admin and not request.user.is_superuser:
        raise PermissionDenied(_("Solo un administrador de empresa puede gestionar roles."))
    if request.method == "POST":
        form = RoleForm(request.POST)
        if form.is_valid():
            role = form.save(commit=False)
            role.company = request.user.company
            role.save()
            messages.success(request, _("Rol creado correctamente."))
            return redirect("accounts:role_list")
    else:
        form = RoleForm()
    return render(request, "accounts/role_form.html", {"form": form, "is_new": True})


@login_required
def role_edit(request, pk):
    if not request.user.is_company_admin and not request.user.is_superuser:
        raise PermissionDenied(_("Solo un administrador de empresa puede gestionar roles."))
    role = get_object_or_404(Role, pk=pk, company=request.user.company)
    if request.method == "POST":
        form = RoleForm(request.POST, instance=role)
        if form.is_valid():
            form.save()
            messages.success(request, _("Rol actualizado correctamente."))
            return redirect("accounts:role_list")
    else:
        form = RoleForm(instance=role)
    return render(request, "accounts/role_form.html", {"form": form, "is_new": False, "role": role})


@login_required
def role_delete(request, pk):
    if not request.user.is_company_admin and not request.user.is_superuser:
        raise PermissionDenied(_("Solo un administrador de empresa puede gestionar roles."))
    role = get_object_or_404(Role, pk=pk, company=request.user.company)
    if request.method == "POST":
        if role.is_default:
            messages.error(request, _("No se puede eliminar un rol por defecto."))
        elif role.users.exists() or role.event_memberships.exists():
            messages.error(request, _("No se puede eliminar un rol que todavía tiene personas asignadas."))
        else:
            role.delete()
            messages.success(request, _("Rol eliminado."))
    return redirect("accounts:role_list")
