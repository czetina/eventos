from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("", views.event_list, name="list"),
    path("nuevo/", views.event_create, name="create"),
    path("<int:pk>/", views.event_detail, name="detail"),
    path("<int:pk>/editar/", views.event_edit, name="edit"),
    path("<int:pk>/itinerario/nuevo/", views.event_session_create, name="session_create"),
    path("<int:pk>/itinerario/<int:session_pk>/eliminar/", views.event_session_delete, name="session_delete"),
    path("<int:pk>/equipo/", views.event_team, name="team"),
    path("<int:pk>/equipo/<int:member_pk>/quitar/", views.event_team_remove, name="team_remove"),
]
