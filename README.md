# econt-control-plane

Control plane multitenant que orquesta **tenants** del SaaS contable: alta/baja/suspensión, versionado de esquema (Alembic), conexión segura **sin secretos en BD**, y auditoría de eventos.  
**DB:** `platform_admin` · **schema:** `control_plane` · **Runtime:** Python 3.12 · **PostgreSQL:** 17

---

## 1) Qué es esto (Resumen)
- **Objetivo:** Registrar y operar clientes (tenants) con su propia BD, controlar **status** y **schema_version**, y exponer APIs internas para provisión y migraciones por lote.
- **Seguridad:** No se guardan contraseñas en la BD; solo la **referencia** (`db_secret_ref`) al Secret Manager.
- **Decisiones base:** ver `docs/adr/ADR-CP-001.md` y `docs/adr/ADR-CP-002.md`.

---

## 2) Stack y estándares
- **Python 3.12**, **FastAPI**, **SQLAlchemy 2 (async)**, **Alembic 1.13**
- **PostgreSQL 17** con **pgcrypto** (obligatoria); `pg_trgm` y `citext` opcionales
- Driver único: **psycopg 3** (`postgresql+psycopg://`)
- Deps: `pyproject.toml` + **uv** (bloqueo reproducible con `uv.lock`)
- CI/CD: GitHub Actions (preflight PG17, migraciones, escaneo de secretos)

---

## 3) Modelo de datos (MVP)
Tablas en `platform_admin.control_plane`:

- **`tenants`**:  
  `id (uuid)`, `slug (unique CI + soft delete)`, `display_name`, `db_name (unique CI + soft delete)`,  
  `db_host`, `db_port`, `db_user`, `db_secret_ref` (**referencia al secreto**),  
  `schema_version`, `app_version?`, `status {'provisioning','active','suspended','deleting'}`,  
  `created_at`, `updated_at`, `deleted_at?`, `billing_plan?`, `contact_email?`, `suspended_reason?`, `maintenance_flag?`.

- **`tenant_events`**:  
  `id`, `tenant_id (FK DEFERRABLE)`, `event_type (FK)`, `actor`, `payload JSONB?`, `created_at`.

- **`event_types`** (catálogo):  
  `provisioned`, `migrated`, `suspended`, `resumed`, `deleting`, `deleted`, `status_changed`, `error`.

- **`tenant_limits`** (opcional 1:1):  
  `tenant_id (PK/FK)`, `max_db_size_mb?`, `max_users?`, `max_attachments_gb?`, `notes?`, `updated_at`.

**Reglas clave**
- PKs con `UUID DEFAULT gen_random_uuid()` (requiere **pgcrypto**).
- **Soft delete**: `deleted_at` en `tenants`.
- **Unicidad case-insensitive con soft delete**:  
  `UNIQUE (lower(slug)) WHERE deleted_at IS NULL`  
  `UNIQUE (lower(db_name)) WHERE deleted_at IS NULL`
- `status` con `CHECK IN ('provisioning','active','suspended','deleting')` y **DEFAULT `'provisioning'`**.
- Triggers `set_updated_at()` en `tenants` y `tenant_limits`.
- Índices operativos: `status`, `(status, updated_at DESC)`, `(tenant_id, created_at DESC)` en `tenant_events`.  
- Opcional: `pg_trgm` (búsquedas por `display_name`), `GIN(jsonb_path_ops)` para `payload`.

---

## 4) Requisitos previos
- **PostgreSQL 17** accesible y **pgcrypto** habilitada.
- **Python 3.12** y **uv** instalado (`pip install uv`).

**Valores locales sugeridos (DEV):**
- Host: `localhost`
- Puerto: `5432`
- Usuario: `postgres`
- Password: `postgres`
- Base: `platform_admin`

---

## 5) Configuración (variables de entorno)
Obligatorias:
- `CONTROL_PLANE_DATABASE_URL=postgresql+psycopg://<USER>:<PASS>@<HOST>:5432/platform_admin`

Recomendadas:
- `ENVIRONMENT={dev|staging|prod}`
- `SECRET_MANAGER_BACKEND={env|mock|vault|aws|gcp|azure}`
- `SECRET_MANAGER_ENDPOINT` (requerida en staging/prod con backend real)

**Seguridad:** No commitear `.env`. Incluye un `.env.example` **sin** valores reales.

---

## 6) Cómo levantar en DEV (API incluida en este repo)
```bash
# 1) Preparar entorno
uv venv && uv sync

# 2) Configurar conexión
export CONTROL_PLANE_DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/platform_admin"

# 3) Migraciones (crea esquema, tablas, índices, triggers)
alembic upgrade head

# 4) Seeds del catálogo event_types (idempotente; según tu organización de migraciones)
# ejemplo si los seeds están en una migración de datos dedicada:
alembic upgrade +1

# 5) Levantar la API (app ya incluida en este repo)
uvicorn app.main:app --reload --port 8001

## 7) Seguridad de secretos

En la BD se guarda solo db_secret_ref (ruta/ARN/clave en Secret Manager).

Backends de secretos: env|mock (solo dev), vault|aws|gcp|azure (staging/prod).

El API obtiene el secreto en runtime y construye el DSN; cache con TTL corto.

8) CI / Quality Gate (MVP)

Preflight Postgres 17 (falla si versión <17; verifica pgcrypto).

Instalación reproducible con uv (uv lock/sync).

alembic upgrade head (idempotente).

Gitleaks (bloquea secretos o .env en el repo).

Guard SQL: db_secret_ref no debe contener ://, @ ni keywords sensibles.

(Opcional) Lint, type-check, tests si la API ya está en el repo.

9) Operación (consultas de salud)

Duplicados efectivos (deleted_at IS NULL) de slug/db_name → deben ser 0.

Tenants sin eventos o provisioning atascados (ventana operativa definida por el equipo).

schema_version ≠ último migrated.payload.to → marcar desalineados.

Coherencia soft delete: si deleted_at ≠ NULL ⇒ status ∈ {deleting,deleted}.

10) Interfaz con el sistema contable (contrato mínimo)

Resolución slug → DSN: leer tenants (filtrando deleted_at IS NULL), obtener password desde Secret Manager por db_secret_ref y construir la URL de conexión.

Política de status:

active → OK;

suspended → HTTP 423;

provisioning|deleting → HTTP 409 (o read-only si se define).

11) Estructura del repo

.
├─ app/                 # FastAPI (routers, services, deps, secrets/)
├─ migrations/          # Alembic (head DDL + seeds event_types)
├─ docs/adr/            # ADR-CP-001, ADR-CP-002
├─ .github/workflows/   # CI (preflight PG17, alembic, gitleaks)
├─ pyproject.toml
├─ alembic.ini
└─ README.md

12) ADRs

docs/adr/ADR-CP-001.md — Modelo de datos, unicidad CI + soft delete, auditoría.

docs/adr/ADR-CP-002.md — Runtime 3.12, psycopg3, migraciones, CI/CD, seguridad de secretos (vigente).

13) Roadmap corto

Provisionar tenant piloto (acme) y registrar evento provisioned.

Resolver tenant → DSN con Secret Manager stub (dev).

Migraciones canary → lote y tablero básico (status/versión).

(Escala) Activar pg_trgm para búsqueda por display_name y particionado mensual de tenant_events al superar umbrales.

