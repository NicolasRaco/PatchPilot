import pytest

from shipping import shipping_cost


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        (dict(weight_kg=1, zone="local"), 5.0),
        (dict(weight_kg=10, zone="national"), 15.0),
        (dict(weight_kg=30, zone="international"), 40.0),
        (dict(weight_kg=1, zone="local", express=True), 7.5),
        (dict(weight_kg=1, zone="international", express=True), 50.0),
        (dict(weight_kg=1, zone="local", fragile=True), 8.0),
        (dict(weight_kg=30, zone="national", member=True), 20.0),
        (dict(weight_kg=1, zone="local", member=True), 5.0),
    ],
)
def test_shipping_cost(kwargs, expected):
    assert shipping_cost(**kwargs) == expected


@pytest.mark.parametrize("weight, zone", [(0, "local"), (1, "mars")])
def test_shipping_cost_rejects_bad_input(weight, zone):
    with pytest.raises(ValueError):
        shipping_cost(weight, zone)
