from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ==== Catalog: event_types ====
class EventType(Base):
    __tablename__ = "event_types"
    __table_args__ = {"schema": "control_plane"}

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)


# ==== Tenants ====
class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("db_port BETWEEN 1 AND 65535", name="tenants_db_port_range_chk"),
        CheckConstraint("schema_version ~ '^[0-9a-f]{12}$'", name="tenants_schema_version_format_chk"),
        CheckConstraint(
            "app_version IS NULL OR app_version ~ '^\\d+\\.\\d+\\.\\d+(-[0-9A-Za-z\\.-]+)?(\\+[0-9A-Za-z\\.-]+)?$'",
            name="tenants_app_version_semver_chk",
        ),
        CheckConstraint("status IN ('provisioning','active','suspended','deleting')", name="tenants_status_chk"),
        CheckConstraint("slug ~ '^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'", name="tenants_slug_format_chk"),
        CheckConstraint("length(display_name) > 0", name="tenants_display_name_not_empty"),
        CheckConstraint("length(db_name) > 0", name="tenants_db_name_not_empty"),
        CheckConstraint("length(db_host) > 0", name="tenants_db_host_not_empty"),
        CheckConstraint("length(db_user) > 0", name="tenants_db_user_not_empty"),
        CheckConstraint("length(db_secret_ref) > 0", name="tenants_db_secret_ref_not_empty"),
        CheckConstraint("updated_at >= created_at", name="tenants_updated_ge_created"),
        {"schema": "control_plane"},
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))

    slug: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)

    db_name: Mapped[str] = mapped_column(Text, nullable=False)
    db_host: Mapped[str] = mapped_column(Text, nullable=False)
    db_port: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("5432"))
    db_user: Mapped[str] = mapped_column(Text, nullable=False)
    db_secret_ref: Mapped[str] = mapped_column(Text, nullable=False)

    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    app_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'provisioning'"))

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    billing_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suspended_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    maintenance_flag: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # relationships
    events: Mapped[list["TenantEvent"]] = relationship(back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True)
    limits: Mapped[Optional["TenantLimit"]] = relationship(back_populates="tenant", uselist=False, cascade="all, delete-orphan", passive_deletes=True)


# ==== Tenant Events ====
class TenantEvent(Base):
    __tablename__ = "tenant_events"
    __table_args__ = {"schema": "control_plane"}

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("control_plane.tenants.id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        Text, ForeignKey("control_plane.event_types.code", deferrable=True, initially="DEFERRED"), nullable=False
    )
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="events")


# ==== Tenant Limits ====
class TenantLimit(Base):
    __tablename__ = "tenant_limits"
    __table_args__ = (
        CheckConstraint("max_db_size_mb IS NULL OR max_db_size_mb >= 0", name="limits_dbsize_nonneg"),
        CheckConstraint("max_users IS NULL OR max_users >= 0", name="limits_users_nonneg"),
        CheckConstraint("max_attachments_gb IS NULL OR max_attachments_gb >= 0", name="limits_attach_nonneg"),
        {"schema": "control_plane"},
    )

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("control_plane.tenants.id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"),
        primary_key=True,
    )
    max_db_size_mb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_users: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_attachments_gb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="limits")
