from django.urls import path

from . import views

app_name = "vendors"

urlpatterns = [
    path("", views.vendor_list, name="list"),
    path("nuevo/", views.vendor_create, name="create"),
    path("evento/<int:event_pk>/agregar/", views.event_vendor_add, name="event_vendor_add"),
    path("evento/<int:event_pk>/quitar/<int:pk>/", views.event_vendor_remove, name="event_vendor_remove"),
]
