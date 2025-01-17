"""api_token_scopes

Revision ID: 651f5419b74d
Revises: 833da8570507
Create Date: 2022-02-28 12:42:55.149046

"""
# revision identifiers, used by Alembic.
revision = '651f5419b74d'
down_revision = '833da8570507'
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Table
from sqlalchemy import Unicode
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm.session import Session

from jupyterhub import orm
from jupyterhub import roles


def upgrade():
    c = op.get_bind()

    tables = sa.inspect(c.engine).get_table_names()

    # oauth codes are short lived, no need to upgrade them
    if 'oauth_code_role_map' in tables:
        op.drop_table('oauth_code_role_map')

    if 'oauth_codes' in tables:
        op.add_column('oauth_codes', sa.Column('scopes', orm.JSONList(), nullable=True))

    if 'api_tokens' not in tables:
        # e.g. upgrade from 1.x, token table dropped
        # no migration to do
        return

    # define new scopes column on API tokens
    op.add_column('api_tokens', sa.Column('scopes', orm.JSONList(), nullable=True))

    if 'api_token_role_map' in tables:
        # redefine the to-be-removed api_token->role relationship
        # so we can run a query on it for the migration
        token_role_map = Table(
            "api_token_role_map",
            orm.Base.metadata,
            Column(
                'api_token_id',
                ForeignKey('api_tokens.id', ondelete='CASCADE'),
                primary_key=True,
            ),
            Column(
                'role_id',
                ForeignKey('roles.id', ondelete='CASCADE'),
                primary_key=True,
            ),
            extend_existing=True,
        )
        orm.APIToken.roles = relationship('Role', secondary='api_token_role_map')

        # tokens have roles, evaluate to scopes
        db = Session(bind=c)
        for token in db.query(orm.APIToken):
            token.scopes = list(roles.roles_to_scopes(token.roles))
        db.commit()
        # drop token-role relationship
        op.drop_table('api_token_role_map')


def downgrade():
    # cannot map permissions from scopes back to roles
    # drop whole api token table (revokes all tokens), which will be recreated on hub start
    op.drop_table('api_tokens')
    op.drop_table('oauth_codes')
