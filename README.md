# EventPlanner

Sistema web para planificación de eventos (bodas, corporativos, etc.), multiempresa (SaaS),
multipaís y multilocación, con checklist de tareas por responsable (jerarquía
planificador → supervisor → encargado) que exige evidencia (foto/documento) y hora
de finalización.

## Stack

- **Backend:** Python 3.12 + Django 6 (arquitectura MVC/MVT)
- **Frontend:** HTML + Bootstrap 5 (CDN) + JavaScript básico
- **Base de datos:** SQLite (`db.sqlite3`)
- **Entorno:** [uv](https://docs.astral.sh/uv/) para gestión de dependencias
- **Multilenguaje:** i18n de Django, español e inglés (archivo `locale/en/LC_MESSAGES/django.po`
  compilado con `polib` porque el binario GNU `gettext` no está disponible en Windows por
  defecto; si luego lo instalas, `makemessages`/`compilemessages` normales también funcionan)
- **Multiempresa:** cada `Company` (empresa/agencia) es un tenant; sus usuarios y eventos
  están aislados de otras empresas.

## Estructura de apps

- `apps.accounts` — Empresa (tenant) y Usuario con rol (`company_admin`, `planner`,
  `supervisor`, `encargado`).
- `apps.events` — Evento (multipaís/multilocación vía `django-countries`), Itinerario
  (`EventSession`, para varias actividades el mismo día en distintos lugares) y Equipo
  del evento (`EventTeamMember`, con jerarquía `reports_to`).
- `apps.tasks` — Tarea (checklist) asignada a un encargado, con fecha/hora límite,
  banderas `requiere_foto`/`requiere_documento`, y `TaskEvidence` (archivo subido +
  hora + quién lo subió). No se puede marcar completada si falta evidencia requerida.
- `apps.vendors` — Proveedores y espacios (venues), reutilizables entre eventos de la
  misma empresa, y su relación contractual con cada evento.
- `apps.notes` — Notas y archivos generales por evento.
- `apps.core` — Panel principal (dashboard) según el rol, plantilla base y navbar.

## Primeros pasos

```bash
# 1. Instalar dependencias (crea .venv automáticamente)
uv sync

# 2. Aplicar migraciones
uv run python manage.py migrate

# 3. Cargar datos de demostración (empresa, usuarios de cada rol, eventos, tareas)
uv run python manage.py seed_demo_data

# 4. Arrancar el servidor
uv run python manage.py runserver
```

Abre http://127.0.0.1:8000/

### Usuarios de demostración (empresa "Bodas Aurora Eventos")

| Usuario      | Contraseña   | Rol                    | Notas                          |
|--------------|--------------|------------------------|---------------------------------|
| `admin`      | `admin123`   | Administrador (superuser) | Acceso a `/admin/`           |
| `planner`    | `planner123` | Planificador           | Crea eventos y tareas           |
| `supervisor` | `super123`   | Supervisor             | Coordina montaje y banquete     |
| `juan`       | `juan123`    | Encargado              | Ve "Mis tareas" (celular)       |
| `maria`      | `maria123`   | Encargado              | Interfaz configurada en inglés  |

Para recrear los datos de demo desde cero: `uv run python manage.py seed_demo_data --reset`

### Crear tu propia empresa

En vez de usar los datos de demo, puedes registrar una empresa nueva desde
`/cuentas/registro/` (crea la empresa y su primer usuario administrador).

## Flujo clave: checklist de tareas con evidencia

1. Un planificador o supervisor crea una tarea dentro de un evento, la asigna a un
   encargado, define fecha/hora límite y marca si requiere foto y/o documento.
2. El encargado entra desde su celular a **Mis tareas** (`/tareas/mis-tareas/`),
   ve sus pendientes ordenadas por fecha, con las atrasadas resaltadas en rojo.
3. Al abrir una tarea, puede subir la evidencia (foto o documento) con un comentario.
4. El botón "Marcar como completada" queda bloqueado por el servidor si la tarea
   requiere evidencia y todavía no se ha subido ningún archivo.
5. Al completarse, se registra automáticamente quién y a qué hora la completó.

## Idiomas

Cada usuario tiene un `idioma preferido` (español/inglés) que se activa automáticamente
al iniciar sesión. También hay un selector de idioma en la barra de navegación.

## Fase 2 (fuera de alcance de esta entrega)

Página web de boda pública, plano de mesas (con póster ilustrado por IA), presupuesto
detallado con exportación a PDF/Excel, lista de invitados e invitaciones digitales,
galería postboda, dominios personalizados y soporte multi-sitio. El modelo de datos
actual (Empresa → Evento → Equipo/Tareas/Proveedores/Notas) está pensado para poder
añadir estos módulos sin rediseñar lo ya construido.
