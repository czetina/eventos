from django.urls import path

from . import views

app_name = "notes"

urlpatterns = [
    path("evento/<int:event_pk>/notas/", views.note_list, name="list"),
    path("evento/<int:event_pk>/notas/<int:pk>/eliminar/", views.note_delete, name="delete"),
    path("evento/<int:event_pk>/archivos/", views.file_list, name="files"),
    path("evento/<int:event_pk>/archivos/<int:pk>/eliminar/", views.file_delete, name="file_delete"),
]
