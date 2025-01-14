"""empty message

Revision ID: c8f64c8333d2
Revises: ffef09e6ddf1
Create Date: 2024-06-14 16:41:02.361125

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8f64c8333d2'
down_revision = 'ffef09e6ddf1'
branch_labels = None
depends_on = None


def upgrade():
    # Add default permissions mappings for formsflow
    op.execute("""
        WITH upsert AS (
            SELECT 1 FROM permission_target WHERE uri = '/*'
        )
        INSERT INTO permission_target (uri)
        SELECT '/*'
        WHERE NOT EXISTS (SELECT 1 FROM upsert);
    """)
    # Change Process group and process models to work with database rather than disk



def downgrade():
    pass
