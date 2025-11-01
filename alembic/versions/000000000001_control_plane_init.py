"""control_plane init (DDL baseline)"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql

# Revision identifiers, used by Alembic.
revision = "000000000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Schema & extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE SCHEMA IF NOT EXISTS control_plane")

    # set_updated_at() trigger function
    op.execute(
        """
        CREATE OR REPLACE FUNCTION control_plane.set_updated_at()
        RETURNS trigger AS $$
        BEGIN
          NEW.updated_at := now();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # Catalog: event_types
    op.create_table(
        "event_types",
        sa.Column("code", sa.Text, primary_key=True),
        sa.Column("description", sa.Text, nullable=False),
        schema="control_plane",
    )

    # Table: tenants
    op.create_table(
        "tenants",
        sa.Column("id", psql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("db_name", sa.Text, nullable=False),
        sa.Column("db_host", sa.Text, nullable=False),
        sa.Column("db_port", sa.Integer, nullable=False, server_default=sa.text("5432")),
        sa.Column("db_user", sa.Text, nullable=False),
        sa.Column("db_secret_ref", sa.Text, nullable=False),
        sa.Column("schema_version", sa.Text, nullable=False),
        sa.Column("app_version", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default=sa.text("'provisioning'")),
        sa.Column("created_at", psql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", psql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", psql.TIMESTAMP(timezone=True), nullable=True),
        # optional extras
        sa.Column("billing_plan", sa.Text, nullable=True),
        sa.Column("contact_email", sa.Text, nullable=True),
        sa.Column("suspended_reason", sa.Text, nullable=True),
        sa.Column("maintenance_flag", sa.Boolean, nullable=True),
        # checks
        sa.CheckConstraint("db_port BETWEEN 1 AND 65535", name="tenants_db_port_range_chk"),
        sa.CheckConstraint("schema_version ~ '^[0-9a-f]{12}$'", name="tenants_schema_version_format_chk"),
        sa.CheckConstraint(
            "app_version IS NULL OR app_version ~ '^\\d+\\.\\d+\\.\\d+(-[0-9A-Za-z\\.-]+)?(\\+[0-9A-Za-z\\.-]+)?$'",
            name="tenants_app_version_semver_chk",
        ),
        sa.CheckConstraint("status IN ('provisioning','active','suspended','deleting')", name="tenants_status_chk"),
        sa.CheckConstraint("slug ~ '^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'", name="tenants_slug_format_chk"),
        sa.CheckConstraint("length(display_name) > 0", name="tenants_display_name_not_empty"),
        sa.CheckConstraint("length(db_name) > 0", name="tenants_db_name_not_empty"),
        sa.CheckConstraint("length(db_host) > 0", name="tenants_db_host_not_empty"),
        sa.CheckConstraint("length(db_user) > 0", name="tenants_db_user_not_empty"),
        sa.CheckConstraint("length(db_secret_ref) > 0", name="tenants_db_secret_ref_not_empty"),
        sa.CheckConstraint("updated_at >= created_at", name="tenants_updated_ge_created"),
        schema="control_plane",
    )

    # Unique indexes (case-insensitive) WITH soft-delete
    op.create_index(
        "uq_tenants_slug_ci_undel",
        "tenants",
        [sa.text("lower(slug)")],
        unique=True,
        schema="control_plane",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_tenants_dbname_ci_undel",
        "tenants",
        [sa.text("lower(db_name)")],
        unique=True,
        schema="control_plane",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Operational indexes
    op.create_index("idx_tenants_status", "tenants", ["status"], unique=False, schema="control_plane")
    op.create_index(
        "idx_tenants_status_updated_desc", "tenants", ["status", "updated_at"], unique=False, schema="control_plane"
    )
    op.create_index(
        "idx_tenants_status_non_active",
        "tenants",
        ["status"],
        unique=False,
        schema="control_plane",
        postgresql_where=sa.text("status <> 'active'"),
    )

    # Trigger for updated_at on tenants
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_tenants_set_updated ON control_plane.tenants;
        CREATE TRIGGER trg_tenants_set_updated
        BEFORE UPDATE ON control_plane.tenants
        FOR EACH ROW
        EXECUTE FUNCTION control_plane.set_updated_at();
        """
    )

    # Table: tenant_events
    op.create_table(
        "tenant_events",
        sa.Column("id", psql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", psql.UUID(as_uuid=False), nullable=False),
        sa.Column("event_type", sa.Text, nullable=False),
        sa.Column("actor", sa.Text, nullable=False),
        sa.Column("payload", psql.JSONB, nullable=True),
        sa.Column("created_at", psql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["control_plane.tenants.id"],
            ondelete="CASCADE",
            deferrable=True,
            initially="DEFERRED",
            name="fk_events_tenant",
        ),
        sa.ForeignKeyConstraint(
            ["event_type"],
            ["control_plane.event_types.code"],
            deferrable=True,
            initially="DEFERRED",
            name="fk_events_type",
        ),
        schema="control_plane",
    )
    op.create_index(
        "idx_tenant_events_tenant_created",
        "tenant_events",
        ["tenant_id", "created_at"],
        unique=False,
        schema="control_plane",
    )
    op.create_index("idx_tenant_events_type", "tenant_events", ["event_type"], unique=False, schema="control_plane")
    op.create_index("idx_tenant_events_created", "tenant_events", ["created_at"], unique=False, schema="control_plane")
    # Optional payload index (commented)
    # op.execute("CREATE INDEX idx_tenant_events_payload ON control_plane.tenant_events USING GIN (payload jsonb_path_ops)")

    # Table: tenant_limits
    op.create_table(
        "tenant_limits",
        sa.Column("tenant_id", psql.UUID(as_uuid=False), primary_key=True),
        sa.Column("max_db_size_mb", sa.Integer, nullable=True),
        sa.Column("max_users", sa.Integer, nullable=True),
        sa.Column("max_attachments_gb", sa.Integer, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("updated_at", psql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["control_plane.tenants.id"],
            ondelete="CASCADE",
            deferrable=True,
            initially="DEFERRED",
            name="fk_limits_tenant",
        ),
        sa.CheckConstraint("max_db_size_mb IS NULL OR max_db_size_mb >= 0", name="limits_dbsize_nonneg"),
        sa.CheckConstraint("max_users IS NULL OR max_users >= 0", name="limits_users_nonneg"),
        sa.CheckConstraint("max_attachments_gb IS NULL OR max_attachments_gb >= 0", name="limits_attach_nonneg"),
        schema="control_plane",
    )

    # Trigger for updated_at on tenant_limits
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_limits_set_updated ON control_plane.tenant_limits;
        CREATE TRIGGER trg_limits_set_updated
        BEFORE UPDATE ON control_plane.tenant_limits
        FOR EACH ROW
        EXECUTE FUNCTION control_plane.set_updated_at();
        """
    )


def downgrade():
    # Drop tenant_limits
    op.execute("DROP TRIGGER IF EXISTS trg_limits_set_updated ON control_plane.tenant_limits")
    op.drop_table("tenant_limits", schema="control_plane")

    # Drop tenant_events
    op.drop_index("idx_tenant_events_created", table_name="tenant_events", schema="control_plane")
    op.drop_index("idx_tenant_events_type", table_name="tenant_events", schema="control_plane")
    op.drop_index("idx_tenant_events_tenant_created", table_name="tenant_events", schema="control_plane")
    op.drop_table("tenant_events", schema="control_plane")

    # Drop tenants (indexes first)
    op.execute("DROP TRIGGER IF EXISTS trg_tenants_set_updated ON control_plane.tenants")
    op.drop_index("idx_tenants_status_non_active", table_name="tenants", schema="control_plane")
    op.drop_index("idx_tenants_status_updated_desc", table_name="tenants", schema="control_plane")
    op.drop_index("idx_tenants_status", table_name="tenants", schema="control_plane")
    op.drop_index("uq_tenants_dbname_ci_undel", table_name="tenants", schema="control_plane")
    op.drop_index("uq_tenants_slug_ci_undel", table_name="tenants", schema="control_plane")
    op.drop_table("tenants", schema="control_plane")

    # Drop event_types
    op.drop_table("event_types", schema="control_plane")
