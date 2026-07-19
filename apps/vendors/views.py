from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from apps.events.views import get_event_or_403

from .forms import EventVendorForm, VendorForm
from .models import EventVendor, Vendor


@login_required
def vendor_list(request):
    vendors = Vendor.objects.filter(company=request.user.company) if request.user.company else Vendor.objects.none()
    category = request.GET.get("category")
    if category:
        vendors = vendors.filter(category=category)
    return render(request, "vendors/vendor_list.html", {
        "vendors": vendors, "category_choices": Vendor.CATEGORY_CHOICES, "active_category": category,
    })


@login_required
def vendor_detail(request, pk):
    vendor = get_object_or_404(Vendor, pk=pk, company=request.user.company)
    return render(request, "vendors/vendor_detail.html", {
        "vendor": vendor,
        "bookings": vendor.event_bookings.select_related("event"),
        "tasks": vendor.tasks.select_related("event").order_by("due_date", "due_time"),
    })


@login_required
def vendor_create(request):
    if not request.user.can_manage_events:
        raise PermissionDenied(_("No tienes permiso para agregar proveedores."))
    if request.method == "POST":
        form = VendorForm(request.POST)
        if form.is_valid():
            vendor = form.save(commit=False)
            vendor.company = request.user.company
            vendor.save()
            messages.success(request, _("Proveedor/espacio agregado."))
            return redirect("vendors:list")
    else:
        form = VendorForm()
    return render(request, "vendors/vendor_form.html", {"form": form})


@login_required
def event_vendor_add(request, event_pk):
    event = get_event_or_403(request.user, event_pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    if request.method == "POST":
        form = EventVendorForm(request.POST, company=request.user.company, event=event)
        if form.is_valid():
            ev = form.save(commit=False)
            ev.event = event
            ev.save()
            messages.success(request, _("Proveedor asociado al evento."))
            return redirect("events:detail", pk=event.pk)
    else:
        form = EventVendorForm(company=request.user.company, event=event)
    return render(request, "vendors/event_vendor_form.html", {"form": form, "event": event, "is_new": True})


@login_required
def event_vendor_edit(request, event_pk, pk):
    event = get_event_or_403(request.user, event_pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    ev = get_object_or_404(EventVendor, pk=pk, event=event)
    if request.method == "POST":
        form = EventVendorForm(request.POST, instance=ev, company=request.user.company, event=event)
        if form.is_valid():
            form.save()
            messages.success(request, _("Proveedor del evento actualizado."))
            return redirect("events:detail", pk=event.pk)
    else:
        form = EventVendorForm(instance=ev, company=request.user.company, event=event)
    return render(request, "vendors/event_vendor_form.html", {"form": form, "event": event, "is_new": False})


@login_required
def event_vendor_remove(request, event_pk, pk):
    event = get_event_or_403(request.user, event_pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    ev = get_object_or_404(EventVendor, pk=pk, event=event)
    if request.method == "POST":
        ev.delete()
        messages.success(request, _("Proveedor quitado del evento."))
    return redirect("events:detail", pk=event.pk)
