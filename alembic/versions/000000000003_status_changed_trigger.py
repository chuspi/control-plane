"""status_changed trigger on tenants"""

from alembic import op

# Revision identifiers
revision = "000000000003"
down_revision = "000000000002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        -- Función que registra un evento si cambia el status
        CREATE OR REPLACE FUNCTION control_plane.log_status_changed()
        RETURNS trigger AS $$
        BEGIN
          IF NEW.status IS DISTINCT FROM OLD.status THEN
            INSERT INTO control_plane.tenant_events (id, tenant_id, event_type, actor, payload)
            VALUES (
              gen_random_uuid(),
              NEW.id,
              'status_changed',
              current_user, -- o 'system-trigger' si prefieres
              jsonb_build_object('from', OLD.status, 'to', NEW.status)
            );
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        -- Trigger AFTER UPDATE OF status
        DROP TRIGGER IF EXISTS trg_tenants_status_changed ON control_plane.tenants;

        CREATE TRIGGER trg_tenants_status_changed
        AFTER UPDATE OF status ON control_plane.tenants
        FOR EACH ROW
        WHEN (OLD.status IS DISTINCT FROM NEW.status)
        EXECUTE FUNCTION control_plane.log_status_changed();
        """
    )


def downgrade():
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_tenants_status_changed ON control_plane.tenants;
        DROP FUNCTION IF EXISTS control_plane.log_status_changed();
        """
    )
