from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("mis-tareas/", views.my_tasks, name="my_tasks"),
    path("completar-varias/", views.task_bulk_complete, name="bulk_complete"),
    path("evento/<int:event_pk>/", views.task_list, name="list"),
    path("evento/<int:event_pk>/nueva/", views.task_create, name="create"),
    path("evento/<int:event_pk>/importar/", views.task_import, name="import"),
    path("evento/<int:event_pk>/importar/confirmar/", views.task_import_confirm, name="import_confirm"),
    path("evento/<int:event_pk>/exportar-guion.ics", views.task_export_guion_ics, name="export_guion_ics"),
    path("guion/<uuid:token>.ics", views.task_export_guion_ics_public, name="export_guion_ics_public"),
    path("evento/<int:event_pk>/cadenas/", views.task_chain_list, name="chain_list"),
    path("evento/<int:event_pk>/cadenas/nueva/", views.task_chain_create, name="chain_create"),
    path("cadenas/<int:pk>/", views.task_chain_detail, name="chain_detail"),
    path("cadenas/<int:pk>/editar/", views.task_chain_edit, name="chain_edit"),
    path("cadenas/<int:pk>/eliminar/", views.task_chain_delete, name="chain_delete"),
    path("cadenas/<int:pk>/agregar-tarea/", views.task_chain_add_task, name="chain_add_task"),
    path("cadenas/<int:pk>/nueva-tarea/", views.task_chain_create_task, name="chain_create_task"),
    path("cadenas/<int:pk>/tareas/<int:task_pk>/quitar/", views.task_chain_remove_task, name="chain_remove_task"),
    path(
        "cadenas/<int:pk>/tareas/<int:task_pk>/mover/<str:direction>/",
        views.task_chain_move, name="chain_move_task",
    ),
    path("<int:pk>/", views.task_detail, name="detail"),
    path("<int:pk>/editar/", views.task_edit, name="edit"),
    path("<int:pk>/eliminar/", views.task_delete, name="delete"),
    path("<int:pk>/evidencia/", views.task_upload_evidence, name="upload_evidence"),
    path("<int:pk>/evidencia/<int:evidence_pk>/eliminar/", views.task_delete_evidence, name="delete_evidence"),
    path("<int:pk>/completar/", views.task_complete, name="complete"),
    path("<int:pk>/cambiar-estado/", views.task_change_status, name="change_status"),
    path("<int:pk>/historial/<int:history_pk>/editar/", views.task_status_history_edit, name="status_history_edit"),
    path("<int:pk>/historial/<int:history_pk>/eliminar/", views.task_status_history_delete, name="status_history_delete"),
]
