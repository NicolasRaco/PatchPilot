import pytest

from fees import late_fee


@pytest.mark.parametrize("args", [(-1, 100), (5, -1)])
def test_negative_inputs_rejected(args):
    with pytest.raises(ValueError):
        late_fee(*args)


def test_zero_balance_no_fee():
    assert late_fee(30, 0) == 0.0


@pytest.mark.parametrize("days", [0, 2, 3])
def test_within_grace_no_fee(days):
    assert late_fee(days, 1000) == 0.0


def test_custom_grace_period():
    assert late_fee(10, 1000, grace_days=10) == 0.0


@pytest.mark.parametrize(
    "days, expected",
    [
        (10, 10.0),   # 1 week at 1%
        (17, 20.0),   # 2 weeks at 1%
        (24, 40.0),   # 3 weeks: 1% + 1% + 2%
        (38, 80.0),   # 5 weeks
        (52, 100.0),  # 7 weeks would be 130, capped at 10%
    ],
)
def test_weekly_steps(days, expected):
    assert late_fee(days, 1000) == expected


def test_tier_discounts():
    assert late_fee(17, 1000, tier="gold") == 10.0
    assert late_fee(17, 1000, tier="silver") == 15.0


def test_repeat_offender_surcharge():
    assert late_fee(17, 1000, prior_late_count=3) == 25.0


def test_minimum_fee():
    assert late_fee(10, 100) == 5.0
