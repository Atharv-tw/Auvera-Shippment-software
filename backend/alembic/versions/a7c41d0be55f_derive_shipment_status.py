"""derive shipment status from the shipment's own evidence

Shipment Status stopped being typed: it is Shipped once the line has a
BL/AWB/FCR number or an actual sailing date, and Planned until then. Existing
rows carry whatever was typed into the sheet ("shipped", "Planned", blank), so
they are recomputed here, and the column is dropped from every row's
``edited_keys`` - a derived column is nobody's manual edit to protect.

Revision ID: a7c41d0be55f
Revises: e1c2b38f3a8b
Create Date: 2026-09-06

"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7c41d0be55f'
down_revision: Union[str, Sequence[str], None] = 'e1c2b38f3a8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Recompute the status; no schema change."""
    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE tracker_rows SET shipment_status = CASE"
        " WHEN (bl_no IS NOT NULL AND bl_no <> '') OR etd IS NOT NULL"
        " THEN 'Shipped' ELSE 'Planned' END"
    ))

    rows = bind.execute(sa.text(
        "SELECT id, edited_keys FROM tracker_rows WHERE edited_keys IS NOT NULL"
    )).fetchall()
    for row_id, edited in rows:
        keys = json.loads(edited) if isinstance(edited, str) else edited
        if not isinstance(keys, list) or "shipment_status" not in keys:
            continue
        keys = [k for k in keys if k != "shipment_status"]
        bind.execute(
            sa.text("UPDATE tracker_rows SET edited_keys = :keys WHERE id = :id"),
            {"keys": json.dumps(keys), "id": row_id},
        )


def downgrade() -> None:
    """The typed values are gone; leaving the computed ones is the honest undo."""
    pass
