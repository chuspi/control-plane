from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, EmailStr, constr

SlugStr = constr(pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
AlembicRev = constr(pattern=r"^[0-9a-f]{12}$")
SemVer = constr(pattern=r"^\d+\.\d+\.\d+(-[0-9A-Za-z\.-]+)?(\+[0-9A-Za-z\.-]+)?$")

# ==== Tenants ====

class TenantBase(BaseModel):
    slug: SlugStr
    display_name: constr(min_length=1)
    db_name: constr(min_length=1)
    db_host: constr(min_length=1)
    db_port: int = 5432
    db_user: constr(min_length=1)
    db_secret_ref: constr(min_length=1)
    schema_version: AlembicRev
    app_version: Optional[SemVer] = None
    status: Optional[str] = Field(default="provisioning", pattern=r"^(provisioning|active|suspended|deleting)$")
    billing_plan: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    suspended_reason: Optional[str] = None
    maintenance_flag: Optional[bool] = None

class TenantCreate(TenantBase):
    pass

class TenantUpdate(BaseModel):
    display_name: Optional[str] = None
    app_version: Optional[SemVer] = None
    status: Optional[str] = Field(default=None, pattern=r"^(provisioning|active|suspended|deleting)$")
    billing_plan: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    suspended_reason: Optional[str] = None
    maintenance_flag: Optional[bool] = None

class TenantOut(BaseModel):
    id: str
    slug: str
    display_name: str
    db_name: str
    db_host: str
    db_port: int
    db_user: str
    db_secret_ref: str
    schema_version: str
    app_version: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    billing_plan: Optional[str] = None
    contact_email: Optional[str] = None
    suspended_reason: Optional[str] = None
    maintenance_flag: Optional[bool] = None

    model_config = {"from_attributes": True}

# ==== Events ====

class TenantEventCreate(BaseModel):
    tenant_id: str
    event_type: str
    actor: str
    payload: Optional[dict] = None

class TenantEventOut(BaseModel):
    id: str
    tenant_id: str
    event_type: str
    actor: str
    payload: Optional[Any] = None
    created_at: datetime
    model_config = {"from_attributes": True}

# ==== Limits ====

class TenantLimitUpsert(BaseModel):
    max_db_size_mb: Optional[int] = None
    max_users: Optional[int] = None
    max_attachments_gb: Optional[int] = None
    notes: Optional[str] = None

class TenantLimitOut(BaseModel):
    tenant_id: str
    max_db_size_mb: Optional[int] = None
    max_users: Optional[int] = None
    max_attachments_gb: Optional[int] = None
    notes: Optional[str] = None
    updated_at: datetime
    model_config = {"from_attributes": True}
