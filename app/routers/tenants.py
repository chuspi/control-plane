from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.control_plane import Tenant, TenantEvent, TenantLimit
from app.schemas.control_plane import (
    TenantCreate,
    TenantOut,
    TenantUpdate,
    TenantEventCreate,
    TenantEventOut,
    TenantLimitUpsert,
    TenantLimitOut,
)

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("", response_model=List[TenantOut])
async def list_tenants(
    q: Optional[str] = Query(default=None, description="Filtro por slug/display_name (ILIKE %q%)"),
    status_eq: Optional[str] = Query(default=None, pattern="^(provisioning|active|suspended|deleting)$"),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Tenant).where(Tenant.deleted_at.is_(None))
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Tenant.slug.ilike(like)) | (Tenant.display_name.ilike(like)))
    if status_eq:
        stmt = stmt.where(Tenant.status == status_eq)
    stmt = stmt.order_by(Tenant.updated_at.desc())
    res = await session.execute(stmt)
    return res.scalars().all()


@router.post("", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
async def create_tenant(payload: TenantCreate, session: AsyncSession = Depends(get_session)):
    tenant = Tenant(**payload.model_dump())
    session.add(tenant)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        # Mensajes amigables para unicidad CI parcial
        if "uq_tenants_slug_ci_undel" in str(e.orig):
            raise HTTPException(status_code=409, detail="slug ya está en uso (tenant activo)")
        if "uq_tenants_dbname_ci_undel" in str(e.orig):
            raise HTTPException(status_code=409, detail="db_name ya está en uso (tenant activo)")
        raise
    await session.refresh(tenant)
    return tenant


@router.get("/{tenant_id}", response_model=TenantOut)
async def get_tenant(tenant_id: str, session: AsyncSession = Depends(get_session)):
    obj = await session.get(Tenant, tenant_id)
    if not obj or obj.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    return obj


@router.patch("/{tenant_id}", response_model=TenantOut)
async def update_tenant(tenant_id: str, payload: TenantUpdate, session: AsyncSession = Depends(get_session)):
    obj = await session.get(Tenant, tenant_id)
    if not obj or obj.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)

    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        if "uq_tenants_slug_ci_undel" in str(e.orig):
            raise HTTPException(status_code=409, detail="slug ya está en uso (tenant activo)")
        if "uq_tenants_dbname_ci_undel" in str(e.orig):
            raise HTTPException(status_code=409, detail="db_name ya está en uso (tenant activo)")
        raise
    await session.refresh(obj)
    return obj


@router.delete("/{tenant_id}", status_code=204)
async def soft_delete_tenant(tenant_id: str, session: AsyncSession = Depends(get_session)):
    obj = await session.get(Tenant, tenant_id)
    if not obj or obj.deleted_at is not None:
        return
    obj.deleted_at = datetime.utcnow()
    obj.status = "deleting"
    await session.commit()


# ---- Events ----

@router.post("/{tenant_id}/events", response_model=TenantEventOut, status_code=201)
async def add_event(tenant_id: str, payload: TenantEventCreate, session: AsyncSession = Depends(get_session)):
    # forzamos tenant_id del path
    event = TenantEvent(
        tenant_id=tenant_id,
        event_type=payload.event_type,
        actor=payload.actor,
        payload=payload.payload,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


@router.get("/{tenant_id}/events", response_model=List[TenantEventOut])
async def list_events(tenant_id: str, session: AsyncSession = Depends(get_session), limit: int = 100):
    stmt = (
        select(TenantEvent)
        .where(TenantEvent.tenant_id == tenant_id)
        .order_by(TenantEvent.created_at.desc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    return res.scalars().all()


# ---- Limits ----

@router.put("/{tenant_id}/limits", response_model=TenantLimitOut)
async def upsert_limits(tenant_id: str, payload: TenantLimitUpsert, session: AsyncSession = Depends(get_session)):
    # UPSERT manual
    existing = await session.get(TenantLimit, tenant_id)
    if existing:
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(existing, k, v)
    else:
        new_lim = TenantLimit(tenant_id=tenant_id, **payload.model_dump())
        session.add(new_lim)
    await session.commit()
    obj = await session.get(TenantLimit, tenant_id)
    return obj
