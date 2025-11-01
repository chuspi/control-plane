"""seed event_types (idempotent)"""

from alembic import op

# Revision identifiers
revision = "000000000002"
down_revision = "000000000001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        INSERT INTO control_plane.event_types (code, description) VALUES
          ('provisioned','Tenant provisioning finished successfully'),
          ('migrated','Schema migration executed'),
          ('suspended','Tenant suspended'),
          ('resumed','Tenant resumed'),
          ('deleting','Deletion process started'),
          ('deleted','Tenant deleted (finalized)'),
          ('status_changed','Tenant status updated'),
          ('error','Operation error')
        ON CONFLICT (code) DO NOTHING;
        """
    )


def downgrade():
    # Por historial/auditoría, no borramos catálogo en downgrade.
    pass
