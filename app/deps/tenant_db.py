import asyncio
import os
from typing import Dict, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.secrets.manager import SecretManager

CONTROL_PLANE_DSN = os.getenv("CONTROL_PLANE_DATABASE_URL", "<REPLACE_ME>")

# Engine del control plane (compartido)
_cp_engine: Optional[AsyncEngine] = None
_cp_lock = asyncio.Lock()

async def get_control_plane_engine() -> AsyncEngine:
    global _cp_engine
    if _cp_engine is None:
        async with _cp_lock:
            if _cp_engine is None:
                _cp_engine = create_async_engine(
                    CONTROL_PLANE_DSN,
                    pool_pre_ping=True,
                    pool_size=5,
                    max_overflow=5,
                    future=True,
                )
    return _cp_engine

# Cache de engines por tenant_id (en memoria de proceso)
_engines: Dict[str, AsyncEngine] = {}
_engines_lock = asyncio.Lock()

async def _resolve_tenant_row(slug: str, cp_engine: AsyncEngine) -> dict:
    q = text("""
        SELECT id, db_host, db_port, db_name, db_user, db_secret_ref, status
        FROM control_plane.tenants
        WHERE lower(slug) = lower(:slug)
          AND deleted_at IS NULL
        LIMIT 1
    """)
    async with cp_engine.connect() as conn:
        row = (await conn.execute(q, {"slug": slug})).mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    status_val = row["status"]
    if status_val == "suspended":
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Tenant suspended")
    if status_val in ("provisioning", "deleting"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Tenant status={status_val}")
    return dict(row)

async def get_tenant_engine_by_slug(slug: str, cp_engine: AsyncEngine, sm: SecretManager) -> AsyncEngine:
    row = await _resolve_tenant_row(slug, cp_engine)
    tenant_id = str(row["id"])

    async with _engines_lock:
        if tenant_id in _engines:
            return _engines[tenant_id]

        # Obtiene password on-demand desde Secret Manager
        password = await sm.get_password(row["db_secret_ref"])

        # Importante: usar asyncpg para conexiones por tenant (alto rendimiento)
        dsn = (
            f"postgresql+psycopg://{row['db_user']}:{password}"
            f"@{row['db_host']}:{row['db_port']}/{row['db_name']}"
        )
        
        engine = create_async_engine(
            dsn,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            future=True,
        )
        _engines[tenant_id] = engine
        return engine

# Dependency FastAPI
async def get_tenant_engine(
    request: Request,
    x_tenant_slug: Optional[str] = Header(default=None, convert_underscores=False),
    cp_engine: AsyncEngine = Depends(get_control_plane_engine),
) -> AsyncEngine:
    slug = x_tenant_slug
    if not slug:
        host = request.headers.get("host", "")
        slug = host.split(".")[0] if host else None
    if not slug:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing tenant slug")

    sm = SecretManager()  # backend y endpoint se toman de env
    return await get_tenant_engine_by_slug(slug, cp_engine, sm)
