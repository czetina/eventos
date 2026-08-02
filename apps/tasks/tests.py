from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Company, Role, User, create_default_roles
from apps.events.models import Event, EventTeamMember

from .models import Task, TaskChain


class TaskChainTestBase(TestCase):
    """Shared fixtures: a company with its four default roles, one user per
    role level (all on the event's team except `outsider_supervisor`, who is a
    supervisor in the same company but NOT a member of this event's team —
    used to prove per-event scoping), and one event."""

    def setUp(self):
        self.company = Company.objects.create(name="Acme Events", country="US")
        roles = create_default_roles(self.company)
        self.planner = User.objects.create_user(
            username="planner", password="pw12345", company=self.company, role=roles[Role.LEVEL_PLANNER],
        )
        self.supervisor = User.objects.create_user(
            username="supervisor", password="pw12345", company=self.company, role=roles[Role.LEVEL_SUPERVISOR],
        )
        self.encargado = User.objects.create_user(
            username="encargado", password="pw12345", company=self.company, role=roles[Role.LEVEL_ENCARGADO],
        )
        self.outsider_supervisor = User.objects.create_user(
            username="outsider", password="pw12345", company=self.company, role=roles[Role.LEVEL_SUPERVISOR],
        )
        self.event = Event.objects.create(
            company=self.company, name="Boda de prueba", client_name="Cliente Prueba",
            country="US", event_date="2026-12-31",
        )
        for user in (self.planner, self.supervisor, self.encargado):
            EventTeamMember.objects.create(event=self.event, user=user, role=user.role)
        # outsider_supervisor is deliberately NOT added to this event's team.

    def make_task(self, title, **kwargs):
        kwargs.setdefault("assigned_to", self.encargado)
        return Task.objects.create(event=self.event, title=title, **kwargs)

    def make_chain(self, name="Reloj de la ceremonia"):
        return TaskChain.objects.create(event=self.event, name=name, created_by=self.planner)


class TaskChainModelTests(TaskChainTestBase):
    def test_create_chain_associates_to_event(self):
        chain = self.make_chain()
        self.assertEqual(chain.event, self.event)
        self.assertIn(chain, self.event.task_chains.all())

    def test_add_task_to_chain_sets_order(self):
        chain = self.make_chain()
        t1 = self.make_task("Comprar reloj", chain=chain, chain_order=1)
        t2 = self.make_task("Grabar reloj", chain=chain, chain_order=2)
        self.assertEqual(list(chain.tasks.order_by("chain_order")), [t1, t2])

    def test_reorder_tasks_no_duplicate_chain_order(self):
        chain = self.make_chain()
        self.make_task("Comprar reloj", chain=chain, chain_order=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.make_task("Grabar reloj", chain=chain, chain_order=1)

    def test_two_chains_can_each_use_order_one(self):
        chain_a = self.make_chain("Cadena A")
        chain_b = self.make_chain("Cadena B")
        self.make_task("Tarea A1", chain=chain_a, chain_order=1)
        self.make_task("Tarea B1", chain=chain_b, chain_order=1)  # must not raise

    def test_remove_task_from_chain_keeps_task(self):
        chain = self.make_chain()
        task = self.make_task("Comprar reloj", chain=chain, chain_order=1)
        task.chain = None
        task.chain_order = None
        task.save(update_fields=["chain", "chain_order"])
        task.refresh_from_db()
        self.assertIsNone(task.chain)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_delete_chain_does_not_delete_tasks(self):
        chain = self.make_chain()
        task = self.make_task("Comprar reloj", chain=chain, chain_order=1)
        chain.tasks.update(chain=None, chain_order=None)
        chain.delete()
        task.refresh_from_db()
        self.assertIsNone(task.chain)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())


class TaskChainCompatibilityTests(TaskChainTestBase):
    def test_existing_task_without_chain_still_works(self):
        task = self.make_task("Tarea suelta")
        self.assertIsNone(task.chain)
        task.status = Task.STATUS_DONE
        task.save()
        self.assertEqual(Task.objects.get(pk=task.pk).status, Task.STATUS_DONE)

    def test_task_can_exist_without_chain(self):
        task = self.make_task("Tarea suelta")
        self.assertIsNone(task.chain_id)
        self.assertIsNone(task.chain_order)

    def test_task_status_history_unaffected_by_chain(self):
        chain = self.make_chain()
        task = self.make_task("Comprar reloj", chain=chain, chain_order=1)
        task.record_status_change(self.planner, note="Importada")
        self.assertEqual(task.status_history.count(), 1)

    def test_task_evidence_unaffected_by_chain(self):
        from .models import TaskEvidence

        chain = self.make_chain()
        task = self.make_task("Comprar reloj", chain=chain, chain_order=1)
        evidence = TaskEvidence.objects.create(task=task, comment="ok")
        self.assertEqual(task.evidences.count(), 1)
        self.assertEqual(evidence.task, task)

    def test_task_progress_percent_counts_all_tasks_regardless_of_chain(self):
        chain = self.make_chain()
        self.make_task("En cadena", chain=chain, chain_order=1, status=Task.STATUS_DONE)
        self.make_task("Suelta", status=Task.STATUS_DONE)
        self.make_task("Suelta pendiente")
        self.assertEqual(self.event.task_progress_percent, 67)


class TaskChainPermissionTests(TaskChainTestBase):
    def test_planner_can_create_edit_delete_chain(self):
        self.client.login(username="planner", password="pw12345")
        resp = self.client.post(
            reverse("tasks:chain_create", args=[self.event.pk]), {"name": "Reloj", "description": ""},
        )
        chain = TaskChain.objects.get(name="Reloj")
        self.assertRedirects(resp, reverse("tasks:chain_detail", args=[chain.pk]))

        resp = self.client.post(
            reverse("tasks:chain_edit", args=[chain.pk]), {"name": "Reloj editado", "description": ""},
        )
        chain.refresh_from_db()
        self.assertEqual(chain.name, "Reloj editado")

        resp = self.client.post(reverse("tasks:chain_delete", args=[chain.pk]))
        self.assertFalse(TaskChain.objects.filter(pk=chain.pk).exists())

    def test_supervisor_on_team_can_manage_chain(self):
        self.client.login(username="supervisor", password="pw12345")
        resp = self.client.post(
            reverse("tasks:chain_create", args=[self.event.pk]), {"name": "Reloj", "description": ""},
        )
        self.assertTrue(TaskChain.objects.filter(name="Reloj").exists())

    def test_supervisor_not_on_team_gets_403(self):
        self.client.login(username="outsider", password="pw12345")
        resp = self.client.get(reverse("tasks:chain_list", args=[self.event.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_encargado_cannot_manage_chain_structure(self):
        chain = self.make_chain()
        self.client.login(username="encargado", password="pw12345")
        resp = self.client.post(
            reverse("tasks:chain_create", args=[self.event.pk]), {"name": "Otra", "description": ""},
        )
        self.assertEqual(resp.status_code, 403)
        resp = self.client.post(reverse("tasks:chain_edit", args=[chain.pk]), {"name": "x", "description": ""})
        self.assertEqual(resp.status_code, 403)

    def test_encargado_can_still_complete_own_task_in_chain(self):
        chain = self.make_chain()
        task = self.make_task("Comprar reloj", chain=chain, chain_order=1, assigned_to=self.encargado)
        self.client.login(username="encargado", password="pw12345")
        resp = self.client.post(reverse("tasks:complete", args=[task.pk]), {})
        task.refresh_from_db()
        self.assertEqual(task.status, Task.STATUS_DONE)


class TaskChainViewTests(TaskChainTestBase):
    def setUp(self):
        super().setUp()
        self.client.login(username="planner", password="pw12345")

    def test_chain_list_view_renders(self):
        self.make_chain()
        resp = self.client.get(reverse("tasks:chain_list", args=[self.event.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Reloj de la ceremonia")

    def test_create_chain_view(self):
        resp = self.client.post(
            reverse("tasks:chain_create", args=[self.event.pk]),
            {"name": "Reloj de la ceremonia", "description": "Ida y vuelta del reloj"},
        )
        chain = TaskChain.objects.get(name="Reloj de la ceremonia")
        self.assertRedirects(resp, reverse("tasks:chain_detail", args=[chain.pk]))

    def test_chain_detail_shows_ordered_tasks(self):
        chain = self.make_chain()
        self.make_task("Grabar reloj", chain=chain, chain_order=2)
        self.make_task("Comprar reloj", chain=chain, chain_order=1)
        resp = self.client.get(reverse("tasks:chain_detail", args=[chain.pk]))
        content = resp.content.decode()
        self.assertLess(content.index("Comprar reloj"), content.index("Grabar reloj"))

    def test_add_existing_task_to_chain(self):
        chain = self.make_chain()
        task = self.make_task("Tarea suelta")
        resp = self.client.post(reverse("tasks:chain_add_task", args=[chain.pk]), {"task_id": task.pk})
        task.refresh_from_db()
        self.assertEqual(task.chain, chain)
        self.assertEqual(task.chain_order, 1)

    def test_create_task_inside_chain_reuses_task_form(self):
        chain = self.make_chain()
        resp = self.client.post(reverse("tasks:chain_create_task", args=[chain.pk]), {
            "title": "Llevar reloj a la ceremonia",
            "assigned_to": self.encargado.pk,
            "requires_photo": "", "requires_video": "", "requires_document": "", "is_guion": "",
        })
        task = Task.objects.get(title="Llevar reloj a la ceremonia")
        self.assertEqual(task.chain, chain)
        self.assertEqual(task.chain_order, 1)
        self.assertRedirects(resp, reverse("tasks:chain_detail", args=[chain.pk]))

    def test_move_task_up_down_swaps_order(self):
        chain = self.make_chain()
        t1 = self.make_task("Comprar reloj", chain=chain, chain_order=1)
        t2 = self.make_task("Grabar reloj", chain=chain, chain_order=2)
        self.client.post(reverse("tasks:chain_move_task", args=[chain.pk, t2.pk, "up"]))
        t1.refresh_from_db()
        t2.refresh_from_db()
        self.assertEqual(t2.chain_order, 1)
        self.assertEqual(t1.chain_order, 2)

    def test_remove_task_from_chain_view(self):
        chain = self.make_chain()
        task = self.make_task("Comprar reloj", chain=chain, chain_order=1)
        self.client.post(reverse("tasks:chain_remove_task", args=[chain.pk, task.pk]))
        task.refresh_from_db()
        self.assertIsNone(task.chain)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_delete_chain_view_unlinks_tasks(self):
        chain = self.make_chain()
        task = self.make_task("Comprar reloj", chain=chain, chain_order=1)
        self.client.post(reverse("tasks:chain_delete", args=[chain.pk]))
        self.assertFalse(TaskChain.objects.filter(pk=chain.pk).exists())
        task.refresh_from_db()
        self.assertIsNone(task.chain)

    def test_task_list_toggle_links_present(self):
        resp = self.client.get(reverse("tasks:list", args=[self.event.pk]))
        self.assertContains(resp, reverse("tasks:chain_list", args=[self.event.pk]))
        self.assertContains(resp, reverse("tasks:chain_create", args=[self.event.pk]))
