"""Add referral and partner program tables

Revision ID: 71fad250dae0
Revises: 7ff48ba73e95
Create Date: 2025-10-04 14:55:11.233496

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71fad250dae0'
down_revision: Union[str, Sequence[str], None] = '7ff48ba73e95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('referral_links',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('owner_id', sa.UUID(), nullable=False),
    sa.Column('link_type', sa.Enum('user', 'partner', name='referrallinktype'), nullable=False),
    sa.Column('percent', sa.Integer(), nullable=True),
    sa.Column('token', sa.String(), nullable=False),
    sa.Column('comment', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_referral_links_owner_id_users')),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token')
    )
    op.create_table('payout_requests',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('partner_id', sa.UUID(), nullable=False),
    sa.Column('amount_minor', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('requested', 'approved', 'rejected', 'paid', name='payoutstatus'), nullable=False),
    sa.Column('requisites_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('processed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['partner_id'], ['users.id'], name=op.f('fk_payout_requests_partner_id_users')),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('purchases',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('amount_minor', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(), nullable=False),
    sa.Column('is_first_for_user', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_purchases_user_id_users')),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('audit_log',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('actor_id', sa.UUID(), nullable=False),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('entity', sa.String(), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=True),
    sa.Column('payload_json', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_audit_log_actor_id_users')),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('roles',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.Enum('user', 'partner', 'admin', name='userrole'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_roles_user_id_users')),
    sa.PrimaryKeyConstraint('user_id', 'role')
    )
    op.create_table('partner_balances',
    sa.Column('partner_id', sa.UUID(), nullable=False),
    sa.Column('balance_minor', sa.Integer(), nullable=False),
    sa.Column('hold_minor', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['partner_id'], ['users.id'], name=op.f('fk_partner_balances_partner_id_users')),
    sa.PrimaryKeyConstraint('partner_id')
    )
    op.create_table('referrals',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('new_user_id', sa.UUID(), nullable=False),
    sa.Column('referrer_type', sa.Enum('user', 'partner', name='referrertype'), nullable=False),
    sa.Column('referrer_id', sa.UUID(), nullable=False),
    sa.Column('ref_link_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['new_user_id'], ['users.id'], name=op.f('fk_referrals_new_user_id_users')),
    sa.ForeignKeyConstraint(['ref_link_id'], ['referral_links.id'], name=op.f('fk_referrals_ref_link_id_referral_links')),
    sa.ForeignKeyConstraint(['referrer_id'], ['users.id'], name=op.f('fk_referrals_referrer_id_users')),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('new_user_id')
    )
    op.create_table('coin_bonus_ledger',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('giver_id', sa.UUID(), nullable=False),
    sa.Column('receiver_id', sa.UUID(), nullable=False),
    sa.Column('purchase_id', sa.UUID(), nullable=False),
    sa.Column('coins', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['giver_id'], ['users.id'], name=op.f('fk_coin_bonus_ledger_giver_id_users')),
    sa.ForeignKeyConstraint(['purchase_id'], ['purchases.id'], name=op.f('fk_coin_bonus_ledger_purchase_id_purchases')),
    sa.ForeignKeyConstraint(['receiver_id'], ['users.id'], name=op.f('fk_coin_bonus_ledger_receiver_id_users')),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('partner_commission_ledger',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('partner_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('purchase_id', sa.UUID(), nullable=False),
    sa.Column('ref_link_id', sa.UUID(), nullable=False),
    sa.Column('base_amount_minor', sa.Integer(), nullable=False),
    sa.Column('percent', sa.Integer(), nullable=False),
    sa.Column('commission_minor', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('reason', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['partner_id'], ['users.id'], name=op.f('fk_partner_commission_ledger_partner_id_users')),
    sa.ForeignKeyConstraint(['purchase_id'], ['purchases.id'], name=op.f('fk_partner_commission_ledger_purchase_id_purchases')),
    sa.ForeignKeyConstraint(['ref_link_id'], ['referral_links.id'], name=op.f('fk_partner_commission_ledger_ref_link_id_referral_links')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_partner_commission_ledger_user_id_users')),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('users', sa.Column('role', sa.Enum('user', 'partner', 'admin', name='userrole'), server_default='user', nullable=False))
    op.add_column('users', sa.Column('referrer_type', sa.Enum('user', 'partner', name='referrertype'), nullable=True))
    op.add_column('users', sa.Column('referrer_id', sa.UUID(), nullable=True))
    op.add_column('users', sa.Column('ref_link_id', sa.UUID(), nullable=True))
    op.create_foreign_key(op.f('fk_users_ref_link_id_referral_links'), 'users', 'referral_links', ['ref_link_id'], ['id'])
    op.create_foreign_key(op.f('fk_users_referrer_id_users'), 'users', 'users', ['referrer_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Правильный порядок: сначала удаляем все, что зависит от ENUM, затем сами ENUM
    op.drop_constraint(op.f('fk_users_referrer_id_users'), 'users', type_='foreignkey')
    op.drop_constraint(op.f('fk_users_ref_link_id_referral_links'), 'users', type_='foreignkey')
    op.drop_column('users', 'ref_link_id')
    op.drop_column('users', 'referrer_id')
    op.drop_column('users', 'referrer_type')
    op.drop_column('users', 'role')

    op.drop_table('partner_commission_ledger')
    op.drop_table('coin_bonus_ledger')
    op.drop_table('referrals')
    op.drop_table('partner_balances')
    op.drop_table('roles')
    op.drop_table('audit_log')
    op.drop_table('purchases')
    op.drop_table('payout_requests')
    op.drop_table('referral_links')

    # Теперь, когда ни одна таблица не использует ENUM, их можно безопасно удалить
    sa.Enum(name='userrole').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='referrertype').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='payoutstatus').drop(op.get_bind(), checkfirst=False)
    sa.Enum(name='referrallinktype').drop(op.get_bind(), checkfirst=False)