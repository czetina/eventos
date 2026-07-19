from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.CompanyLoginView.as_view(), name="login"),
    path("logout/", views.CompanyLogoutView.as_view(), name="logout"),
    path("registro/", views.register_company, name="register_company"),
    path("equipo/", views.team_list, name="team_list"),
    path("equipo/nuevo/", views.team_create, name="team_create"),
    path("equipo/<int:pk>/editar/", views.team_edit, name="team_edit"),
    path("equipo/<int:pk>/eliminar/", views.team_delete, name="team_delete"),
    path("perfil/", views.profile, name="profile"),
    path("roles/", views.role_list, name="role_list"),
    path("roles/nuevo/", views.role_create, name="role_create"),
    path("roles/<int:pk>/editar/", views.role_edit, name="role_edit"),
    path("roles/<int:pk>/eliminar/", views.role_delete, name="role_delete"),
]
