from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("", views.event_list, name="list"),
    path("nuevo/", views.event_create, name="create"),
    path("<int:pk>/", views.event_detail, name="detail"),
    path("<int:pk>/editar/", views.event_edit, name="edit"),
    path("<int:pk>/eliminar/", views.event_delete, name="delete"),
    path("<int:pk>/itinerario/nuevo/", views.event_session_create, name="session_create"),
    path("<int:pk>/itinerario/<int:session_pk>/editar/", views.event_session_edit, name="session_edit"),
    path("<int:pk>/itinerario/<int:session_pk>/eliminar/", views.event_session_delete, name="session_delete"),
    path("<int:pk>/itinerario/eliminar-varias/", views.event_session_bulk_delete, name="session_bulk_delete"),
    path("<int:pk>/itinerario/importar/", views.event_session_import, name="session_import"),
    path("<int:pk>/itinerario/importar/confirmar/", views.event_session_import_confirm, name="session_import_confirm"),
    path("<int:pk>/equipo/", views.event_team, name="team"),
    path("<int:pk>/equipo/<int:member_pk>/quitar/", views.event_team_remove, name="team_remove"),
    path("<int:pk>/cortejo/", views.event_wedding_party, name="wedding_party"),
    path("<int:pk>/cortejo/<int:member_pk>/editar/", views.event_wedding_party_edit, name="wedding_party_edit"),
    path("<int:pk>/cortejo/<int:member_pk>/quitar/", views.event_wedding_party_remove, name="wedding_party_remove"),
    path("cortejo/listas/", views.wedding_party_type_list, name="wedding_party_type_list"),
    path("cortejo/listas/nueva/", views.wedding_party_type_create, name="wedding_party_type_create"),
    path("cortejo/listas/<int:pk>/editar/", views.wedding_party_type_edit, name="wedding_party_type_edit"),
    path("cortejo/listas/<int:pk>/eliminar/", views.wedding_party_type_delete, name="wedding_party_type_delete"),
    path("<int:pk>/planograma/", views.event_processional, name="processional"),
    path("<int:pk>/planograma/<int:entry_pk>/editar/", views.event_processional_edit, name="processional_edit"),
    path("<int:pk>/planograma/<int:entry_pk>/quitar/", views.event_processional_remove, name="processional_remove"),
    path("<int:pk>/comidas/", views.event_meals, name="meals"),
    path("<int:pk>/comidas/<int:meal_pk>/editar/", views.event_meals_edit, name="meals_edit"),
    path("<int:pk>/comidas/<int:meal_pk>/quitar/", views.event_meals_remove, name="meals_remove"),
    path("<int:pk>/reportes/itinerario/", views.report_itinerary, name="report_itinerary"),
    path("<int:pk>/reportes/tareas/", views.report_tasks, name="report_tasks"),
    path("<int:pk>/reportes/historial/", views.report_status_history, name="report_status_history"),
    path("planograma/publico/<uuid:token>/", views.processional_public, name="processional_public"),
]
