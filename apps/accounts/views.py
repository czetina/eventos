from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from .forms import CompanyRegistrationForm, LoginForm, ProfileForm, TeamMemberEditForm, TeamMemberForm
from .models import User


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
    return user.is_superuser or user.role in (User.ROLE_COMPANY_ADMIN, User.ROLE_PLANNER)


@login_required
def team_list(request):
    if not request.user.company:
        return render(request, "accounts/team_list.html", {"members": []})
    members = User.objects.filter(company=request.user.company).order_by("role", "first_name")
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
