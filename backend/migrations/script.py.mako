"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# Alembic 版本标识符，请勿手动修改
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """升级迁移：执行 schema 变更。"""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """回滚迁移：撤销 schema 变更。"""
    ${downgrades if downgrades else "pass"}
