"""promote tracker columns

Revision ID: 248e5769e287
Revises: f209a0994828
Create Date: 2026-08-21 22:32:22.793412

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import json
from datetime import date, datetime

# Frozen at the time this migration was written - deliberately NOT imported from
# app.services.tracker_map, so a later edit to that registry cannot retroactively
# change what this migration did.
TRACKER_TYPES = {
    "company_code": "text",
    "customer_name": "text",
    "factory_name": "text",
    "division": "text",
    "buyer_po": "text",
    "colour": "text",
    "style_no": "text",
    "buyer_po_delivery_date": "date",
    "factory_delivery_date": "date",
    "mode": "text",
    "fob_or_cf": "text",
    "order_qty": "number",
    "ship_qty": "number",
    "pkgs_ctns": "number",
    "buyer_currency": "text",
    "buyer_net_price": "number",
    "buyer_total_value": "number",
    "vendor_terms": "text",
    "factory_price": "number",
    "vendor_total_value": "number",
    "price_difference": "number",
    "factory_inv_no": "text",
    "factory_inv_date": "date",
    "auvera_inv_no": "text",
    "etd": "date",
    "eta": "date",
    "bl_no": "text",
    "bl_date": "date",
    "docs_received": "date",
    "docs_due_date": "date",
    "docs_delay_days": "number",
    "forwarder": "text",
    "item": "text",
    "short_extra_qty": "number",
    "factory_payment_due_date": "date",
    "shipment_status": "text",
    "delay_shipment": "number",
    "buyer_payment_due_date": "date",
    "remarks": "text",
    "factory_payment_terms_status": "text",
    "buyer_payment_terms_status": "text",
    "final_inspection_date": "date",
    "pod": "text",
    "preship_docs_sent": "date",
    "buyer_approved": "date",
    "booking_no": "text",
    "booking_date": "date",
    "approval_carting_do_date": "date",
    "actual_ho_date": "date",
    "container_no": "text",
    "container_size": "text",
    "lcl_fcl": "text",
    "vessel": "text",
    "voyage": "text",
    "docs_shared_customer": "text",
    "docs_shared_date": "date",
}

_DATE_FORMATS = ["%Y-%m-%d", "%d-%b-%Y", "%d-%b-%y", "%d/%m/%Y", "%d/%m/%y", "%d.%m.%Y"]


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    return None


def _as_number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _tracker_table():
    cols = [sa.column("id"), sa.column("raw", sa.JSON), sa.column("data", sa.JSON)]
    cols += [sa.column(k) for k in TRACKER_TYPES]
    return sa.table("tracker_rows", *cols)


def _backfill_into_columns() -> None:
    """Copy the JSON blob into the new real columns, keeping anything unmodelled.

    A value that will not coerce (a malformed date, say) is left in ``raw``
    rather than dropped - the ``data`` property merges ``raw`` last, so the
    original is still what the API returns. Nothing is lost.
    """
    conn = op.get_bind()
    tracker = _tracker_table()
    rows = conn.execute(sa.text("SELECT id, data FROM tracker_rows")).fetchall()
    for row_id, blob in rows:
        values = json.loads(blob) if isinstance(blob, str) else (blob or {})
        if not values:
            continue
        payload, leftovers = {}, {}
        for key, value in values.items():
            kind = TRACKER_TYPES.get(key)
            if kind is None:
                leftovers[key] = value          # unmodelled -> raw
                continue
            if kind == "date":
                coerced = _as_date(value)
            elif kind == "number":
                coerced = _as_number(value)
            else:
                coerced = None if value is None else str(value)
            if coerced is None and value not in (None, ""):
                leftovers[key] = value          # would not coerce -> keep verbatim
                continue
            payload[key] = coerced
        payload["raw"] = leftovers
        conn.execute(tracker.update().where(tracker.c.id == row_id).values(**payload))


def _backfill_into_blob() -> None:
    """Reverse of the above, so `alembic downgrade` does not lose the tracker."""
    conn = op.get_bind()
    tracker = _tracker_table()
    cols = ", ".join(TRACKER_TYPES)
    rows = conn.execute(sa.text(f"SELECT id, raw, {cols} FROM tracker_rows")).fetchall()
    for row in rows:
        row_id, raw = row[0], row[1]
        raw = json.loads(raw) if isinstance(raw, str) else (raw or {})
        out = {}
        for key, value in zip(TRACKER_TYPES, row[2:]):
            if value is None:
                continue
            out[key] = value.isoformat() if isinstance(value, (date, datetime)) else value
        out.update(raw)
        # `data` is a JSON column - hand it the dict and let SQLAlchemy encode,
        # or it gets encoded twice and comes back out as a string.
        conn.execute(tracker.update().where(tracker.c.id == row_id).values(data=out))


# revision identifiers, used by Alembic.
revision: str = '248e5769e287'
down_revision: Union[str, Sequence[str], None] = 'f209a0994828'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Three steps, and the order is the whole point: the new columns must
    # exist before the blob can be copied into them, and the blob must survive
    # until the copy is done. Autogenerate put the drop in the same batch as
    # the adds, which would have destroyed `data` before the backfill ran.
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('tracker_rows', schema=None) as batch_op:
        batch_op.add_column(sa.Column('company_code', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('customer_name', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('factory_name', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('division', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('buyer_po_delivery_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('factory_delivery_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('mode', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('fob_or_cf', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('order_qty', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('ship_qty', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('pkgs_ctns', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('buyer_currency', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('buyer_net_price', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('buyer_total_value', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('vendor_terms', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('factory_price', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('vendor_total_value', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('price_difference', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('factory_inv_no', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('factory_inv_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('auvera_inv_no', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('etd', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('eta', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('bl_no', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('bl_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('docs_received', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('docs_due_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('docs_delay_days', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('forwarder', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('item', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('short_extra_qty', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('factory_payment_due_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('shipment_status', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('delay_shipment', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('buyer_payment_due_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('remarks', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('factory_payment_terms_status', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('buyer_payment_terms_status', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('final_inspection_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('pod', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('preship_docs_sent', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('buyer_approved', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('booking_no', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('booking_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('approval_carting_do_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('actual_ho_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('container_no', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('container_size', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('lcl_fcl', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('vessel', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('voyage', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('docs_shared_customer', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('docs_shared_date', sa.Date(), nullable=True))
        # NOT NULL needs a default to land on rows that already exist; the
        # default is dropped again below so the DB matches the model exactly
        # (an unmatched server_default would show up as drift).
        batch_op.add_column(
            sa.Column('raw', sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
        )
        batch_op.create_index(batch_op.f('ix_tracker_rows_buyer_po_delivery_date'), ['buyer_po_delivery_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_tracker_rows_etd'), ['etd'], unique=False)
        batch_op.create_index(batch_op.f('ix_tracker_rows_factory_name'), ['factory_name'], unique=False)
        batch_op.create_index(batch_op.f('ix_tracker_rows_shipment_status'), ['shipment_status'], unique=False)

    # ### end Alembic commands ###


    with op.batch_alter_table('tracker_rows', schema=None) as batch_op:
        batch_op.alter_column('raw', server_default=None)

    _backfill_into_columns()

    with op.batch_alter_table('tracker_rows', schema=None) as batch_op:
        batch_op.drop_column('data')


def downgrade() -> None:
    """Downgrade schema."""
    # Mirror image: bring `data` back and refill it from the columns before
    # those columns disappear, so a rollback does not lose the tracker.
    with op.batch_alter_table('tracker_rows', schema=None) as batch_op:
        batch_op.add_column(sa.Column('data', sa.JSON(), nullable=True))
    _backfill_into_blob()

    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('tracker_rows', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tracker_rows_shipment_status'))
        batch_op.drop_index(batch_op.f('ix_tracker_rows_factory_name'))
        batch_op.drop_index(batch_op.f('ix_tracker_rows_etd'))
        batch_op.drop_index(batch_op.f('ix_tracker_rows_buyer_po_delivery_date'))
        batch_op.drop_column('raw')
        batch_op.drop_column('docs_shared_date')
        batch_op.drop_column('docs_shared_customer')
        batch_op.drop_column('voyage')
        batch_op.drop_column('vessel')
        batch_op.drop_column('lcl_fcl')
        batch_op.drop_column('container_size')
        batch_op.drop_column('container_no')
        batch_op.drop_column('actual_ho_date')
        batch_op.drop_column('approval_carting_do_date')
        batch_op.drop_column('booking_date')
        batch_op.drop_column('booking_no')
        batch_op.drop_column('buyer_approved')
        batch_op.drop_column('preship_docs_sent')
        batch_op.drop_column('pod')
        batch_op.drop_column('final_inspection_date')
        batch_op.drop_column('buyer_payment_terms_status')
        batch_op.drop_column('factory_payment_terms_status')
        batch_op.drop_column('remarks')
        batch_op.drop_column('buyer_payment_due_date')
        batch_op.drop_column('delay_shipment')
        batch_op.drop_column('shipment_status')
        batch_op.drop_column('factory_payment_due_date')
        batch_op.drop_column('short_extra_qty')
        batch_op.drop_column('item')
        batch_op.drop_column('forwarder')
        batch_op.drop_column('docs_delay_days')
        batch_op.drop_column('docs_due_date')
        batch_op.drop_column('docs_received')
        batch_op.drop_column('bl_date')
        batch_op.drop_column('bl_no')
        batch_op.drop_column('eta')
        batch_op.drop_column('etd')
        batch_op.drop_column('auvera_inv_no')
        batch_op.drop_column('factory_inv_date')
        batch_op.drop_column('factory_inv_no')
        batch_op.drop_column('price_difference')
        batch_op.drop_column('vendor_total_value')
        batch_op.drop_column('factory_price')
        batch_op.drop_column('vendor_terms')
        batch_op.drop_column('buyer_total_value')
        batch_op.drop_column('buyer_net_price')
        batch_op.drop_column('buyer_currency')
        batch_op.drop_column('pkgs_ctns')
        batch_op.drop_column('ship_qty')
        batch_op.drop_column('order_qty')
        batch_op.drop_column('fob_or_cf')
        batch_op.drop_column('mode')
        batch_op.drop_column('factory_delivery_date')
        batch_op.drop_column('buyer_po_delivery_date')
        batch_op.drop_column('division')
        batch_op.drop_column('factory_name')
        batch_op.drop_column('customer_name')
        batch_op.drop_column('company_code')

    # ### end Alembic commands ###
