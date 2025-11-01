from app import settings
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text
from app.routers.tenants import router as tenants_router


from app.deps.tenant_db import get_tenant_engine

app = FastAPI(title="Control Plane API")

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/tenants/ping")
async def ping_tenant(engine: AsyncEngine = Depends(get_tenant_engine)):
    # Ejecuta una consulta trivial en la BD del tenant
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"ok": True}

app.include_router(tenants_router)
