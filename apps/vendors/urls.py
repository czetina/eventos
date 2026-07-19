from django.urls import path

from . import views

app_name = "vendors"

urlpatterns = [
    path("", views.vendor_list, name="list"),
    path("nuevo/", views.vendor_create, name="create"),
    path("<int:pk>/", views.vendor_detail, name="detail"),
    path("evento/<int:event_pk>/agregar/", views.event_vendor_add, name="event_vendor_add"),
    path("evento/<int:event_pk>/editar/<int:pk>/", views.event_vendor_edit, name="event_vendor_edit"),
    path("evento/<int:event_pk>/quitar/<int:pk>/", views.event_vendor_remove, name="event_vendor_remove"),
]
