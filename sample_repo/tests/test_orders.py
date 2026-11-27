import pytest

from orders import order_total, validate_order


def test_empty_order_rejected():
    with pytest.raises(ValueError):
        order_total([])


@pytest.mark.parametrize("items", [[(-1, 1)], [(10, 0)], [(10, -2)]])
def test_bad_items_rejected(items):
    with pytest.raises(ValueError):
        order_total(items)


@pytest.mark.parametrize(
    "items, customer, expected",
    [
        ([(10, 2)], "regular", 25.0),
        ([(100, 1)], "vip", 90.0),
        ([(100, 1)], "member", 95.0),
    ],
)
def test_customer_discounts(items, customer, expected):
    assert order_total(items, customer_type=customer) == expected


def test_unknown_customer_type_rejected():
    with pytest.raises(ValueError):
        order_total([(10, 1)], customer_type="gold")


def test_bulk_discount():
    assert order_total([(10, 10)]) == 100.0


def test_save5_coupon():
    assert order_total([(50, 1)], coupon="SAVE5") == 50.0


def test_half_coupon_over_100():
    assert order_total([(200, 1)], coupon="HALF") == 105.0


def test_half_coupon_needs_over_100():
    with pytest.raises(ValueError):
        order_total([(100, 1)], coupon="HALF")


def test_unknown_coupon_rejected():
    with pytest.raises(ValueError):
        order_total([(10, 1)], coupon="FOO")


def test_discount_rate_is_capped():
    assert order_total([(30, 10)], customer_type="vip", coupon="HALF") == 125.0


def test_shipping_zones():
    assert order_total([(100, 1)], shipping_zone="local") == 105.0
    assert order_total([(100, 1)], shipping_zone="remote") == 120.0
    assert order_total([(100, 1)], shipping_zone="pickup") == 100.0


def test_total_never_negative():
    assert order_total([(1, 1)], coupon="SAVE5", shipping_zone="pickup") == 0


def test_result_is_rounded():
    assert order_total([(19.999, 1)], shipping_zone="pickup") == 20.0


GOOD = {"id": "A1", "email": "a@b.com", "items": [{"sku": "X", "qty": 2}]}


def test_valid_order_has_no_errors():
    assert validate_order(GOOD) == []


def test_non_dict_rejected():
    assert validate_order("nope") == ["order must be a dict"]


def test_missing_id():
    assert validate_order({**GOOD, "id": ""}) == ["missing id"]


@pytest.mark.parametrize("email", ["abc", "@b.com", "a@"])
def test_bad_email(email):
    assert validate_order({**GOOD, "email": email}) == ["bad email"]


@pytest.mark.parametrize("items", [None, []])
def test_no_items(items):
    assert validate_order({**GOOD, "items": items}) == ["no items"]


def test_item_missing_sku():
    assert validate_order({**GOOD, "items": [{"qty": 1}]}) == ["item 0: missing sku"]


@pytest.mark.parametrize("qty", [0, -1, "3"])
def test_item_bad_qty(qty):
    assert validate_order({**GOOD, "items": [{"sku": "X", "qty": qty}]}) == ["item 0: bad qty"]


def test_item_qty_too_large():
    assert validate_order({**GOOD, "items": [{"sku": "X", "qty": 101}]}) == ["item 0: qty too large"]


def test_express_only_in_us():
    assert validate_order({**GOOD, "express": True, "country": "CA"}) == ["express only in US"]
    assert validate_order({**GOOD, "express": True, "country": "US"}) == []
    assert validate_order({**GOOD, "country": "CA"}) == []


def test_errors_accumulate_in_order():
    assert validate_order({}) == ["missing id", "bad email", "no items"]
