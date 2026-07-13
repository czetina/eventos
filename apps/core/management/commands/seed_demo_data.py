import datetime
import io

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Company, User
from apps.events.models import Event, EventSession, EventTeamMember
from apps.notes.models import Note
from apps.tasks.models import Task, TaskEvidence
from apps.vendors.models import EventVendor, Vendor


def _placeholder_png():
    """A tiny 1x1 PNG so demo evidence has a real image file, without needing Pillow drawing."""
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
        b"\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
    )


class Command(BaseCommand):
    help = "Crea datos de demostración: empresa, usuarios de cada rol, eventos multipaís y tareas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Elimina la empresa de demostración 'Bodas Aurora Eventos' antes de recrearla.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            deleted, _ = Company.objects.filter(name="Bodas Aurora Eventos").delete()
            if deleted:
                self.stdout.write(self.style.WARNING("Datos de demo anteriores eliminados."))

        if Company.objects.filter(name="Bodas Aurora Eventos").exists():
            self.stdout.write(self.style.WARNING(
                "La empresa de demo ya existe. Usa --reset para recrearla."
            ))
            return

        company = Company.objects.create(
            name="Bodas Aurora Eventos", country="MX", city="Ciudad de México",
            phone="+52 55 1234 5678", email="hola@bodasaurora.demo",
        )

        admin = User.objects.create_user(
            username="admin", password="admin123", email="admin@bodasaurora.demo",
            first_name="Laura", last_name="Aurora", company=company,
            role=User.ROLE_COMPANY_ADMIN, preferred_language="es",
            is_staff=True, is_superuser=True,
        )
        planner = User.objects.create_user(
            username="planner", password="planner123", email="planner@bodasaurora.demo",
            first_name="Diego", last_name="Ramírez", company=company,
            role=User.ROLE_PLANNER, preferred_language="es",
        )
        supervisor = User.objects.create_user(
            username="supervisor", password="super123", email="supervisor@bodasaurora.demo",
            first_name="Marcela", last_name="Solís", company=company,
            role=User.ROLE_SUPERVISOR, preferred_language="es",
        )
        juan = User.objects.create_user(
            username="juan", password="juan123", email="juan@bodasaurora.demo",
            first_name="Juan", last_name="Pérez", company=company,
            role=User.ROLE_ENCARGADO, phone="+52 55 1111 2222", preferred_language="es",
        )
        maria = User.objects.create_user(
            username="maria", password="maria123", email="maria@bodasaurora.demo",
            first_name="María", last_name="López", company=company,
            role=User.ROLE_ENCARGADO, phone="+52 55 3333 4444", preferred_language="en",
        )

        today = datetime.date.today()

        wedding = Event.objects.create(
            company=company, name="Boda de Ana y Luis", event_type=Event.TYPE_WEDDING,
            client_name="Ana Torres y Luis Medina", client_phone="+52 55 9876 5432",
            client_email="ana.luis@example.com", country="MX", city="Ciudad de México",
            venue_name="Hacienda Los Álamos", venue_address="Av. Reforma 123, CDMX",
            event_date=today + datetime.timedelta(days=21),
            start_time=datetime.time(16, 0), end_time=datetime.time(23, 59),
            status=Event.STATUS_CONFIRMED, planner=planner, created_by=planner,
            description="Boda de 150 invitados con ceremonia religiosa y recepción al aire libre.",
        )
        corporate = Event.objects.create(
            company=company, name="Lanzamiento Producto ACME", event_type=Event.TYPE_CORPORATE,
            client_name="ACME Corp.", client_email="eventos@acme.example.com",
            country="CO", city="Bogotá", venue_name="Centro de Convenciones Ágora",
            venue_address="Calle 26 #69, Bogotá", event_date=today + datetime.timedelta(days=10),
            start_time=datetime.time(9, 0), end_time=datetime.time(14, 0),
            status=Event.STATUS_PLANNING, planner=planner, created_by=admin,
            description="Evento corporativo de lanzamiento con 300 asistentes.",
        )
        past_event = Event.objects.create(
            company=company, name="Boda de Carla y Pedro", event_type=Event.TYPE_WEDDING,
            client_name="Carla Gómez y Pedro Ruiz", country="ES", city="Madrid",
            venue_name="Finca La Encina", venue_address="Camino Real 45, Madrid",
            event_date=today - datetime.timedelta(days=5),
            status=Event.STATUS_DONE, planner=planner, created_by=planner,
        )

        EventSession.objects.bulk_create([
            EventSession(event=wedding, title="Ceremonia religiosa", venue_name="Parroquia San Rafael",
                         start_time=datetime.time(16, 0), end_time=datetime.time(17, 0), order=1),
            EventSession(event=wedding, title="Cóctel de bienvenida", venue_name="Jardín principal",
                         start_time=datetime.time(17, 30), end_time=datetime.time(19, 0), order=2),
            EventSession(event=wedding, title="Recepción y banquete", venue_name="Salón Los Álamos",
                         start_time=datetime.time(19, 30), end_time=datetime.time(23, 59), order=3),
        ])

        for event in (wedding, corporate):
            EventTeamMember.objects.get_or_create(
                event=event, user=planner, defaults={"role_in_event": EventTeamMember.ROLE_PLANNER}
            )
        sup_membership, _ = EventTeamMember.objects.get_or_create(
            event=wedding, user=supervisor,
            defaults={"role_in_event": EventTeamMember.ROLE_SUPERVISOR, "area": "Montaje y banquete"},
        )
        juan_membership, _ = EventTeamMember.objects.get_or_create(
            event=wedding, user=juan,
            defaults={
                "role_in_event": EventTeamMember.ROLE_ENCARGADO, "area": "Montaje",
                "reports_to": sup_membership,
            },
        )
        maria_membership, _ = EventTeamMember.objects.get_or_create(
            event=wedding, user=maria,
            defaults={
                "role_in_event": EventTeamMember.ROLE_ENCARGADO, "area": "Insumos y bebidas",
                "reports_to": sup_membership,
            },
        )

        task_mesas = Task.objects.create(
            event=wedding, title="Revisar instalación de mesas y sillas",
            description="Confirmar que las 15 mesas redondas y sillas Tiffany estén acomodadas según el plano.",
            category="Montaje", assigned_to=juan, supervisor=supervisor,
            due_date=wedding.event_date, due_time=datetime.time(13, 0),
            requires_photo=True, created_by=supervisor,
        )
        task_licor = Task.objects.create(
            event=wedding, title="Recepción de licor",
            description="Recibir y verificar el pedido de bebidas del proveedor y subir el remito.",
            category="Insumos", assigned_to=maria, supervisor=supervisor,
            due_date=wedding.event_date - datetime.timedelta(days=1), due_time=datetime.time(10, 0),
            requires_document=True, created_by=supervisor,
        )
        Task.objects.create(
            event=wedding, title="Coordinar prueba de sonido",
            category="Logística", assigned_to=juan, supervisor=supervisor,
            due_date=wedding.event_date, due_time=datetime.time(15, 0),
            created_by=supervisor,
        )
        Task.objects.create(
            event=wedding, title="Confirmar montaje floral con proveedor",
            category="Decoración", assigned_to=maria, supervisor=supervisor,
            due_date=today - datetime.timedelta(days=1), due_time=datetime.time(9, 0),
            requires_photo=True, created_by=supervisor,
        )

        task_mesas.status = Task.STATUS_DONE
        from django.utils import timezone
        task_mesas.completed_at = timezone.now()
        task_mesas.completed_by = juan
        task_mesas.save()
        TaskEvidence.objects.create(
            task=task_mesas, uploaded_by=juan, comment="Mesas y sillas listas según plano.",
            file=ContentFile(_placeholder_png(), name="montaje_mesas.png"),
        )

        vendor_banquete = Vendor.objects.create(
            company=company, name="Banquetes El Buen Sabor", category=Vendor.CATEGORY_CATERING,
            contact_name="Rosa Jiménez", phone="+52 55 2222 3333",
        )
        vendor_licor = Vendor.objects.create(
            company=company, name="Distribuidora La Cava", category=Vendor.CATEGORY_LIQUOR,
            contact_name="Óscar Vega", phone="+52 55 4444 5555",
        )
        EventVendor.objects.create(
            event=wedding, vendor=vendor_banquete, contract_amount=85000, deposit_paid=30000,
            status=EventVendor.STATUS_CONFIRMED,
        )
        EventVendor.objects.create(
            event=wedding, vendor=vendor_licor, contract_amount=22000, deposit_paid=22000,
            status=EventVendor.STATUS_PAID,
        )

        Note.objects.create(
            event=wedding, author=planner, pinned=True,
            content="Los novios pidieron confirmar el menú vegetariano para 12 invitados.",
        )

        self.stdout.write(self.style.SUCCESS("Datos de demostración creados con éxito.\n"))
        self.stdout.write("Empresa: Bodas Aurora Eventos\n")
        self.stdout.write("Usuarios (usuario / contraseña / rol):\n")
        self.stdout.write("  admin / admin123 / Administrador de empresa\n")
        self.stdout.write("  planner / planner123 / Planificador\n")
        self.stdout.write("  supervisor / super123 / Supervisor\n")
        self.stdout.write("  juan / juan123 / Encargado (ve 'Mis tareas' en el celular)\n")
        self.stdout.write("  maria / maria123 / Encargado (interfaz en inglés)\n")
