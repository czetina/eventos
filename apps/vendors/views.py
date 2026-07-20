from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.events.views import get_event_or_403

from .forms import EventVendorForm, VendorCategoryForm, VendorDeactivateForm, VendorForm, VendorPaymentForm
from .models import EventVendor, Vendor, VendorCategory, VendorPayment, create_default_vendor_categories


@login_required
def vendor_list(request):
    create_default_vendor_categories(request.user.company) if request.user.company else None
    vendors = Vendor.objects.filter(company=request.user.company) if request.user.company else Vendor.objects.none()
    category = request.GET.get("category")
    if category:
        vendors = vendors.filter(category_id=category)
    category_choices = VendorCategory.objects.filter(company=request.user.company) if request.user.company else []
    return render(request, "vendors/vendor_list.html", {
        "vendors": vendors, "category_choices": category_choices, "active_category": category,
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
    create_default_vendor_categories(request.user.company)
    if request.method == "POST":
        form = VendorForm(request.POST, company=request.user.company)
        if form.is_valid():
            vendor = form.save(commit=False)
            vendor.company = request.user.company
            vendor.save()
            messages.success(request, _("Proveedor/espacio agregado."))
            return redirect("vendors:list")
    else:
        form = VendorForm(company=request.user.company)
    return render(request, "vendors/vendor_form.html", {"form": form, "is_new": True})


@login_required
def vendor_edit(request, pk):
    if not request.user.can_manage_events:
        raise PermissionDenied(_("No tienes permiso para editar proveedores."))
    vendor = get_object_or_404(Vendor, pk=pk, company=request.user.company)
    if request.method == "POST":
        form = VendorForm(request.POST, instance=vendor, company=request.user.company)
        if form.is_valid():
            form.save()
            messages.success(request, _("Proveedor actualizado."))
            return redirect("vendors:detail", pk=vendor.pk)
    else:
        form = VendorForm(instance=vendor, company=request.user.company)
    return render(request, "vendors/vendor_form.html", {"form": form, "is_new": False, "vendor": vendor})


@login_required
def vendor_delete(request, pk):
    if not request.user.can_manage_events:
        raise PermissionDenied(_("No tienes permiso para eliminar proveedores."))
    vendor = get_object_or_404(Vendor, pk=pk, company=request.user.company)
    if request.method == "POST":
        if vendor.event_bookings.exists() or vendor.tasks.exists():
            messages.error(request, _(
                "No se puede eliminar: está asignado a algún evento o tarea. Dalo de baja en su lugar."
            ))
            return redirect("vendors:detail", pk=vendor.pk)
        vendor.delete()
        messages.success(request, _("Proveedor eliminado."))
        return redirect("vendors:list")
    return redirect("vendors:detail", pk=vendor.pk)


@login_required
def vendor_deactivate(request, pk):
    if not request.user.can_manage_events:
        raise PermissionDenied(_("No tienes permiso para dar de baja proveedores."))
    vendor = get_object_or_404(Vendor, pk=pk, company=request.user.company)
    if request.method == "POST":
        form = VendorDeactivateForm(request.POST, instance=vendor)
        if form.is_valid():
            v = form.save(commit=False)
            v.is_active = False
            v.save()
            messages.success(request, _("Proveedor dado de baja."))
            return redirect("vendors:detail", pk=vendor.pk)
    else:
        form = VendorDeactivateForm(instance=vendor, initial={"deactivated_on": timezone.localdate()})
    return render(request, "vendors/vendor_deactivate_form.html", {"form": form, "vendor": vendor})


@login_required
def vendor_reactivate(request, pk):
    if not request.user.can_manage_events:
        raise PermissionDenied(_("No tienes permiso para reactivar proveedores."))
    vendor = get_object_or_404(Vendor, pk=pk, company=request.user.company)
    if request.method == "POST":
        vendor.is_active = True
        vendor.deactivated_on = None
        vendor.save(update_fields=["is_active", "deactivated_on"])
        messages.success(request, _("Proveedor reactivado."))
    return redirect("vendors:detail", pk=vendor.pk)


@login_required
def vendor_category_list(request):
    if not request.user.can_manage_events:
        raise PermissionDenied(_("No tienes permiso para gestionar categorías de proveedores."))
    create_default_vendor_categories(request.user.company)
    categories = VendorCategory.objects.filter(company=request.user.company)
    return render(request, "vendors/vendor_category_list.html", {"categories": categories})


@login_required
def vendor_category_create(request):
    if not request.user.can_manage_events:
        raise PermissionDenied(_("No tienes permiso para gestionar categorías de proveedores."))
    if request.method == "POST":
        form = VendorCategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.company = request.user.company
            category.save()
            messages.success(request, _("Categoría creada correctamente."))
            return redirect("vendors:category_list")
    else:
        form = VendorCategoryForm()
    return render(request, "vendors/vendor_category_form.html", {"form": form, "is_new": True})


@login_required
def vendor_category_edit(request, pk):
    if not request.user.can_manage_events:
        raise PermissionDenied(_("No tienes permiso para gestionar categorías de proveedores."))
    category = get_object_or_404(VendorCategory, pk=pk, company=request.user.company)
    if request.method == "POST":
        form = VendorCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, _("Categoría actualizada correctamente."))
            return redirect("vendors:category_list")
    else:
        form = VendorCategoryForm(instance=category)
    return render(request, "vendors/vendor_category_form.html", {"form": form, "is_new": False, "category": category})


@login_required
def vendor_category_delete(request, pk):
    if not request.user.can_manage_events:
        raise PermissionDenied(_("No tienes permiso para gestionar categorías de proveedores."))
    category = get_object_or_404(VendorCategory, pk=pk, company=request.user.company)
    if request.method == "POST":
        if category.vendors.exists():
            messages.error(request, _("No se puede eliminar una categoría que todavía tiene proveedores asignados."))
        else:
            category.delete()
            messages.success(request, _("Categoría eliminada."))
    return redirect("vendors:category_list")


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
    return render(request, "vendors/event_vendor_form.html", {
        "form": form, "event": event, "event_vendor": ev, "is_new": False,
        "payments": ev.payments.all(),
    })


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


@login_required
def event_vendor_payment_add(request, event_pk, pk):
    event = get_event_or_403(request.user, event_pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    ev = get_object_or_404(EventVendor, pk=pk, event=event)
    if request.method == "POST":
        form = VendorPaymentForm(request.POST, request.FILES)
        if form.is_valid():
            payment = form.save(commit=False)
            already_paid = ev.deposit_paid
            completes_balance = (already_paid + payment.amount) >= ev.contract_amount and ev.contract_amount > 0
            if completes_balance and not payment.document:
                form.add_error("document", _(
                    "Este abono completa el saldo del proveedor — sube el documento de soporte."
                ))
            else:
                payment.event_vendor = ev
                payment.created_by = request.user
                payment.save()
                ev.recompute_deposit_paid()
                messages.success(request, _("Abono registrado."))
                return redirect("vendors:event_vendor_edit", event_pk=event.pk, pk=ev.pk)
    else:
        form = VendorPaymentForm(initial={"date": timezone.localdate()})
    return render(request, "vendors/vendor_payment_form.html", {"form": form, "event": event, "event_vendor": ev})


@login_required
def event_vendor_payment_remove(request, event_pk, pk, payment_pk):
    event = get_event_or_403(request.user, event_pk)
    if not request.user.can_manage_events:
        raise PermissionDenied
    ev = get_object_or_404(EventVendor, pk=pk, event=event)
    payment = get_object_or_404(VendorPayment, pk=payment_pk, event_vendor=ev)
    if request.method == "POST":
        payment.delete()
        ev.recompute_deposit_paid()
        messages.success(request, _("Abono eliminado."))
    return redirect("vendors:event_vendor_edit", event_pk=event.pk, pk=ev.pk)
