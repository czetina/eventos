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
    path("<int:pk>/", views.task_detail, name="detail"),
    path("<int:pk>/editar/", views.task_edit, name="edit"),
    path("<int:pk>/evidencia/", views.task_upload_evidence, name="upload_evidence"),
    path("<int:pk>/completar/", views.task_complete, name="complete"),
    path("<int:pk>/cambiar-estado/", views.task_change_status, name="change_status"),
    path("<int:pk>/historial/<int:history_pk>/editar/", views.task_status_history_edit, name="status_history_edit"),
    path("<int:pk>/historial/<int:history_pk>/eliminar/", views.task_status_history_delete, name="status_history_delete"),
]
