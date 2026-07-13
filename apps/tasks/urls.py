from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("mis-tareas/", views.my_tasks, name="my_tasks"),
    path("evento/<int:event_pk>/", views.task_list, name="list"),
    path("evento/<int:event_pk>/nueva/", views.task_create, name="create"),
    path("<int:pk>/", views.task_detail, name="detail"),
    path("<int:pk>/evidencia/", views.task_upload_evidence, name="upload_evidence"),
    path("<int:pk>/completar/", views.task_complete, name="complete"),
]
