from django.urls import path

from . import views

app_name = "vendors"

urlpatterns = [
    path("", views.vendor_list, name="list"),
    path("nuevo/", views.vendor_create, name="create"),
    path("categorias/", views.vendor_category_list, name="category_list"),
    path("categorias/nueva/", views.vendor_category_create, name="category_create"),
    path("categorias/<int:pk>/editar/", views.vendor_category_edit, name="category_edit"),
    path("categorias/<int:pk>/eliminar/", views.vendor_category_delete, name="category_delete"),
    path("<int:pk>/", views.vendor_detail, name="detail"),
    path("<int:pk>/editar/", views.vendor_edit, name="edit"),
    path("<int:pk>/eliminar/", views.vendor_delete, name="delete"),
    path("<int:pk>/baja/", views.vendor_deactivate, name="deactivate"),
    path("<int:pk>/reactivar/", views.vendor_reactivate, name="reactivate"),
    path("evento/<int:event_pk>/agregar/", views.event_vendor_add, name="event_vendor_add"),
    path("evento/<int:event_pk>/editar/<int:pk>/", views.event_vendor_edit, name="event_vendor_edit"),
    path("evento/<int:event_pk>/quitar/<int:pk>/", views.event_vendor_remove, name="event_vendor_remove"),
    path("evento/<int:event_pk>/<int:pk>/abonos/nuevo/", views.event_vendor_payment_add, name="event_vendor_payment_add"),
    path(
        "evento/<int:event_pk>/<int:pk>/abonos/<int:payment_pk>/editar/",
        views.event_vendor_payment_edit, name="event_vendor_payment_edit",
    ),
    path(
        "evento/<int:event_pk>/<int:pk>/abonos/<int:payment_pk>/eliminar/",
        views.event_vendor_payment_remove, name="event_vendor_payment_remove",
    ),
]
