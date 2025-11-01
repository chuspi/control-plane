# ADR-CP-002 — Control Plane MVP (runtime, datos, migraciones, CI/CD y seguridad de secretos)

**Estado:** Aprobado  
**Fecha:** 2025-10-31  
**Ámbito:** Control plane multitenant (PostgreSQL + SQLAlchemy 2 + Alembic + FastAPI)  
**Sustituye / amplía:** ADR-CP-001 (este documento consolida el estado actual)

---

## 1) Contexto
Se requiere un **control plane** que orqueste tenants (alta/baja, versión de esquema, conexión) **sin almacenar secretos**. El MVP debe ser estable, auditable y listo para CI/CD. La plataforma estandariza en **Python 3.12**, **PostgreSQL 17** y **gestión de dependencias con `pyproject.toml` + `uv`**.

---

## 2) Decisiones

### 2.1 Runtime / dependencias
- **Python:** 3.12 (local, Docker y CI).
- **ORM:** SQLAlchemy 2.x (async).
- **Migraciones:** Alembic 1.13.x (DDL explícito).
- **Driver PostgreSQL (único):** **psycopg 3** (`postgresql+psycopg://`), sin `psycopg2` ni `asyncpg`.
- **Gestión de deps:** `pyproject.toml` con rangos PEP 440 (`~=`) y **lock** con **`uv`** (`uv.lock`).
- **Servidor HTTP:** FastAPI + Uvicorn.

### 2.2 Base de datos (PostgreSQL 17)
- **DB:** `platform_admin`. **Schema:** `control_plane`.
- **Extensiones:** `pgcrypto` (requerida); `pg_trgm` y `citext` opcionales.
- **PKs:** `UUID DEFAULT gen_random_uuid()`.
- **Soft delete:** `deleted_at` en `tenants`.
- **Unicidad case-insensitive + soft delete:** índices únicos **parciales** sobre `lower(slug)` y `lower(db_name)` **WHERE deleted_at IS NULL**.
- **Auditoría mínima:** `tenant_events` (FKs DEFERRABLE, payload JSONB).
- **Cuotas opcionales:** `tenant_limits` (1:1).
- **Triggers:** `set_updated_at()`; opcional `status_changed` (auto-evento al cambiar `status`).
- **Checks:** `status` ∈ {provisioning, active, suspended, deleting}; `schema_version` (12 hex Alembic); `app_version` (SemVer); formatos/longitudes.

### 2.3 Seguridad de secretos
- En la DB sólo **`db_secret_ref`** (ruta/identificador). **Nunca** contraseñas en claro.
- **Dev:** backends `env|mock` permitidos.
- **Staging/Prod:** **obligatorio** backend real (`vault|aws|gcp|azure`) y `SECRET_MANAGER_ENDPOINT`.
- Bloqueo en arranque: `app/settings.py` + validación en `app/secrets/manager.py`.
- **Repo:** `.env` ignorado; CI falla si detecta `.env` o secretos (Gitleaks).

### 2.4 CI/CD
- **GitHub Actions:**
  - Servicio Postgres **17**.
  - **Preflight**: falla si versión < 17, asegura `pgcrypto` y `schema`.
  - `uv venv/lock/sync` para instalación reproducible.
  - `alembic upgrade head`.
  - **Gitleaks** (escaneo de secretos, bloqueante).
  - Guard: fallo si `.env` está commiteado.
  - Check SQL: `db_secret_ref` no contiene secretos/URLs.
  - Build de imagen Docker (sin push por ahora).
- **Docker:** `python:3.12-slim` + `uv` (instala desde `uv.lock`, sin `requirements.txt`).

---

## 3) Modelo de datos (resumen)
**Entidades núcleo**
- `tenants(id, slug, display_name, db_name, db_host, db_port, db_user, db_secret_ref, schema_version, app_version?, status, created_at, updated_at, deleted_at?, billing_plan?, contact_email?, suspended_reason?, maintenance_flag?)`
- `tenant_events(id, tenant_id, event_type, actor, payload?, created_at)`
- `event_types(code, description)`
- `tenant_limits(tenant_id PK/FK, max_db_size_mb?, max_users?, max_attachments_gb?, notes?, updated_at)`

**Relaciones**
- `tenants` 1─N `tenant_events`
- `tenants` 1─1 `tenant_limits` (opcional)

**Índices clave**
- `UNIQUE (lower(slug)) WHERE deleted_at IS NULL`
- `UNIQUE (lower(db_name)) WHERE deleted_at IS NULL`
- Operacionales: `(status)`, `(status, updated_at)`, en eventos `(tenant_id, created_at)`.

---

## 4) Migraciones y guardrails
- **Head** crea `pgcrypto`, `control_plane`, tablas, checks, triggers y **índices únicos parciales**.
- Seeds idempotentes (`event_types` con `ON CONFLICT DO NOTHING`).
- Trigger opcional `status_changed`.
- **Guardrails**: DDL transaccional, constraints, FKs DEFERRABLE, validaciones regex.
- En futuras migraciones con índices grandes: `SET LOCAL lock_timeout/statement_timeout` y `CREATE INDEX CONCURRENTLY` (en migración separada).

---

## 5) API de control plane (MVP)
- FastAPI (async) + SQLAlchemy 2 (async) sobre DSN **`+psycopg`**.
- CRUD de `tenants` (list, create, get, patch, soft-delete), `tenant_events` (list, create), `tenant_limits` (upsert).
- Mensajes 409 amigables ante conflictos de unicidad **CI+soft delete**.
- **Multitenancy de negocio (resolver tenant→DB)**: **postergado** a integración real de Secret Manager (el stub está listo).

---

## 6) Seguridad y cumplimiento
- **Repositorio:** `.env` ignorado; ejemplo `.env.example` con placeholders `${VAR}`/`<REPLACE_ME>`.
- **CI:**
  - Falla si `.env` está versionado.
  - **Gitleaks** (bloqueante).
  - Check SQL: `db_secret_ref` no debe parecer secreto/URL (`://`, `@`, keywords).
- **Código:**
  - `app/settings.py` impide `env|mock` en `staging/prod`.
  - `app/secrets/manager.py` exige `SECRET_MANAGER_ENDPOINT` con backend real en `staging/prod`.
  - No se loguean DSNs con credenciales (recomendación de redacción).

---

## 7) Alternativas consideradas
- **`asyncpg`**: descartado para evitar duplicar drivers; se adopta **psycopg 3** único.
- **`requirements.txt` estricto**: sustituido por `pyproject.toml` + `uv.lock` (export a `requirements.txt` sólo si un entorno legacy lo exige).
- **RLS + single DB** vs **DB-per-tenant**: fuera del alcance del control plane; este diseño es neutral respecto al data plane.

---

## 8) Consecuencias
- **Simplicidad operativa:** un solo driver (psycopg3) y lock reproducible (`uv.lock`).
- **Seguridad reforzada:** sin secretos at rest; CI bloquea `.env` y secretos.
- **Evolución segura:** índices parciales permiten reuso de `slug/db_name` con soft delete; FKs DEFERRABLE facilitan bulk ops.
- **Portabilidad:** DDL explícito, seeds idempotentes, preflight CI con Postgres 17.

---

## 9) Plan de despliegue / pasos
1. **Local/Dev:** `uv venv`, `uv lock`, `uv sync`, `alembic upgrade head`, levantar API.
2. **CI:** ejecutar workflow `ci.yml` (Postgres 17, preflight, migraciones, escaneo de secretos).
3. **Docker:** build con Dockerfile `uv`; inyección de `CONTROL_PLANE_DATABASE_URL` en runtime.
4. **Staging/Prod (cuando aplique Secret Manager):** configurar `ENVIRONMENT=staging|prod`, `SECRET_MANAGER_BACKEND=vault|aws|gcp|azure` y `SECRET_MANAGER_ENDPOINT`.

---

## 10) Métricas / Validación
- **DB:** `SHOW server_version` (17.x), presencia de `pgcrypto`.
- **`tenants`**: inserts/updates sin errores de constraints; unicidad CI efectiva; `status_changed` registra eventos (si trigger activo).
- **Seguridad:** Gitleaks OK; paso “Assert no secrets in db_secret_ref” en verde; `.env` no versionado.
- **CI:** `alembic upgrade head` idempotente; imagen Docker build OK.

---

## 11) Anexos (rutas y placeholders)
- Variables:
  - `CONTROL_PLANE_DATABASE_URL=postgresql+psycopg://<USER>:<PASSWORD>@<HOST>:5432/platform_admin`
  - `ENVIRONMENT={dev|staging|prod}`
  - `SECRET_MANAGER_BACKEND={env|mock|vault|aws|gcp|azure}`
  - `SECRET_MANAGER_ENDPOINT=<REPLACE_ME>` (requerida en staging/prod con backend real)
- **Prohibido** commitear `.env`; usar `.env.example` y Secret Manager en entornos no-dev.
