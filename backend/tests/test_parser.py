from app.services.order_parser import detect_kind, parse_customer_order, parse_vendor_order

from .conftest import SAMPLES


def test_customer_order_parses_header_and_lines():
    p = str(SAMPLES / "Order Confirmation-D579-Style-10242608-20271108- sent-27-06-2026.xlsx")
    assert detect_kind(p) == "customer"
    d = parse_customer_order(p)
    assert d["header"]["order_number"] == "D579"
    assert d["header"]["currency"] == "GBP"
    assert len(d["lines"]) == 4
    first = d["lines"][0]
    assert first["style_no"] == "10242608"
    assert first["colour"] == "Black"
    assert first["quantity"] == 400
    assert first["price"] == 8.7
    assert first["total_spent"] == 3480.0
    # second line carries the TopUp
    assert d["lines"][1]["topup"] == "T1"


def test_quantity_falls_back_to_size_sum():
    p = str(SAMPLES / "Customer-Order ^N D579-27-04-2026.xlsx")
    d = parse_customer_order(p)
    line = d["lines"][0]
    assert line["quantity"] == sum(line["sizes"].values())


def test_vendor_order_splits_into_blocks():
    p = str(SAMPLES / "different sheets" / "Vendor-Order-D652-18.04.2026.xlsx")
    assert detect_kind(p, name_hint="Vendor-Order-D652.xlsx") == "vendor"
    d = parse_vendor_order(p)
    assert len(d["blocks"]) == 2
    suppliers = {b["header"]["supplier"] for b in d["blocks"]}
    assert suppliers == {"ENDOW EXPORTS", "CRIMSON"}
    # vendor layout: price present, no total_spent column
    endow = next(b for b in d["blocks"] if b["header"]["supplier"] == "ENDOW EXPORTS")
    assert endow["lines"][0]["price"] == 8.0
    assert "total_spent" not in endow["lines"][0]
