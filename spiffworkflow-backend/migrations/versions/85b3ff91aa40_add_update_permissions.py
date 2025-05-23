"""add update permissions

Revision ID: 85b3ff91aa40
Revises: 345ccc676bbf
Create Date: 2025-05-19 16:14:41.546971

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '85b3ff91aa40'
down_revision = '345ccc676bbf'
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Check and insert into Group table
    permission_targets = {}
    groups = {}
    for target_uri in ['/*', '/task-filters', '/task-filters/*', '/task/*', '/key/*', '/process-definition/*',
                       '/process-definition', '/deployment/create']:
        permission_target_id = op.get_bind().execute(sa.text(f"""
                    SELECT id FROM permission_target WHERE uri = '{target_uri}';
                """)).fetchone()

        permission_targets[target_uri] = permission_target_id[0]

    for group in ['camunda-admin', 'view_filters', 'view_tasks', 'manage_tasks', 'create_submissions', 'view_designs',
                  'create_designs']:
        group_id = op.get_bind().execute(sa.text(f"""
                        INSERT INTO "group" (identifier)
                        SELECT '{group}' 
                        WHERE NOT EXISTS (SELECT id FROM "group" WHERE identifier = '{group}')
                        RETURNING id;
                    """)).fetchone()

        if group_id is None:
            group_id = op.get_bind().execute(sa.text(f"""
                            SELECT id FROM "group" WHERE identifier = '{group}';
                        """)).fetchone()
        group_id = group_id[0]
        groups[group] = {"id": group_id}

        # INSERT Into principal
        principal_id = op.get_bind().execute(sa.text(f"""
                                INSERT INTO principal (group_id)
                                SELECT {group_id}
                                WHERE NOT EXISTS (SELECT id FROM principal WHERE group_id = :group_id)
                                RETURNING id;
                            """), {'group_id': group_id}).fetchone()

        if principal_id is None:
            principal_id = op.get_bind().execute(sa.text(f"""
                                    SELECT id FROM principal WHERE group_id = :group_id
                                    
                                """), {'group_id': group_id}).fetchone()
        groups[group].update({"principal_id": principal_id[0]})

    # Insert into permission_assignment
    for permission_target_uri in permission_targets.keys():
        if permission_target_uri == '/*':
            # Allowed for all reads and create for camunda-admin
            for grant_type in ["update"]:
                principal_id = groups['camunda-admin'].get("principal_id")
                _insert_into_permission_assignment(grant_type, permission_targets[permission_target_uri], principal_id)

        elif permission_target_uri in ["/task-filters", "/task-filters/*", "/task/*"]:
            # Allowed for all reads and create for view_tasks
            for grant_type in ["update"]:
                principal_id = groups['view_tasks'].get("principal_id")
                _insert_into_permission_assignment(grant_type, permission_targets[permission_target_uri], principal_id)
        elif permission_target_uri in ["/key/*"]:
            # Allowed for all reads and create for create_submissions
            for grant_type in ["update"]:
                principal_id = groups['create_submissions'].get("principal_id")
                _insert_into_permission_assignment(grant_type, permission_targets[permission_target_uri], principal_id)
        elif permission_target_uri in ["/process-definition/*", "/process-definition"]:
            # Allowed for all reads and create for view_designs
            for grant_type in ["update"]:
                principal_id = groups['view_designs'].get("principal_id")
                _insert_into_permission_assignment(grant_type, permission_targets[permission_target_uri], principal_id)
        elif permission_target_uri in ["/deployment/create"]:
            # Allowed for all reads and create for create_designs
            for grant_type in ["update"]:
                principal_id = groups['create_designs'].get("principal_id")
                _insert_into_permission_assignment(grant_type, permission_targets[permission_target_uri], principal_id)


def _insert_into_permission_assignment(grant_type, permission_target_id, principal_id):
    permission_assignment = op.get_bind().execute(sa.text(f"""
                                            SELECT id FROM permission_assignment 
                                            WHERE principal_id = {principal_id} 
                                            AND permission_target_id = {permission_target_id}
                                            AND grant_type = 'permit'
                                            AND permission = '{grant_type}';
                                        """)).fetchone()
    if not permission_assignment:
        op.get_bind().execute(sa.text(f"""INSERT INTO permission_assignment 
                                                (principal_id, permission_target_id, grant_type, permission)
                                                VALUES ({principal_id}, {permission_target_id}, 'permit', '{grant_type}');
                                            """))


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
