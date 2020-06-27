"""add new user role

Revision ID: f8a44acd0e41
Revises: 526aa91cac98
Create Date: 2019-10-01 14:04:02.769564+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from faraday.server.models import User

revision = 'f8a44acd0e41'
down_revision = '526aa91cac98'
branch_labels = None
depends_on = None

old_types = User.ROLES.remove('asset_owner')
new_types = list(set(User.ROLES + ['asset_owner']))
new_options = sorted(new_types)

old_type = sa.Enum(*User.ROLES, name='user_roles')
new_type = sa.Enum(*new_options, name='user_roles')
tmp_type = sa.Enum(*new_options, name='_user_roles')

tcr = sa.sql.table('faraday_user',
                   sa.Column('role', new_type, nullable=False))


def upgrade():
    tmp_type.create(op.get_bind(), checkfirst=False)
    op.execute('ALTER TABLE faraday_user ALTER COLUMN role TYPE _user_roles'
               ' USING role::text::_user_roles')
    old_type.drop(op.get_bind(), checkfirst=False)
    # Create and convert to the "new" status type
    new_type.create(op.get_bind(), checkfirst=False)
    op.execute('ALTER TABLE faraday_user ALTER COLUMN role TYPE user_roles'
               ' USING role::text::user_roles')
    tmp_type.drop(op.get_bind(), checkfirst=False)


def downgrade():
    # Convert 'asset_owner' status into 'client'
    op.execute(tcr.update().where(tcr.c.role == u'asset_owner')
               .values(status='client'))
    # Create a temporary "_role" type, convert and drop the "new" type
    tmp_type.create(op.get_bind(), checkfirst=False)
    op.execute('ALTER TABLE faraday_user ALTER COLUMN status TYPE _user_roles'
               ' USING role::text::_user_roles')
    new_type.drop(op.get_bind(), checkfirst=False)
    # Create and convert to the "old" role type
    old_type.create(op.get_bind(), checkfirst=False)
    op.execute('ALTER TABLE faraday_user ALTER COLUMN role TYPE user_roles'
               ' USING role::text::user_roles')
    tmp_type.drop(op.get_bind(), checkfirst=False)
