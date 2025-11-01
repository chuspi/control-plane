from alembic import op
revision = "000000000004"; down_revision = "000000000003"
def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
def downgrade(): pass
