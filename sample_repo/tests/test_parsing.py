import pytest

from parsing import normalize_phone, parse_duration


@pytest.mark.parametrize(
    "text, expected",
    [
        ("90s", 90),
        ("1h 30m", 5400),
        ("2d", 172800),
        ("1H30M", 5400),
        ("1h30m10s", 5410),
        ("10 m", 600),
        ("-2d", -172800),
    ],
)
def test_parse_duration_ok(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text", [None, "", "   ", "m", "5m5m", "5x", "5"])
def test_parse_duration_rejected(text):
    with pytest.raises(ValueError):
        parse_duration(text)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("(613) 555-0123", "+16135550123"),
        ("1-613-555-0123", "+16135550123"),
        ("+44 20 7946 0958", "+442079460958"),
    ],
)
def test_normalize_phone_ok(raw, expected):
    assert normalize_phone(raw) == expected


def test_normalize_phone_custom_default_country():
    assert normalize_phone("2079460958", default_country="44") == "+442079460958"
    assert normalize_phone("7 9161234567", default_country="7") == "+79161234567"


@pytest.mark.parametrize(
    "raw",
    [None, "", "---", "613-555-0123 ext", "1+2", "12345", "26135550123", "+1234567", "+1234567890123456"],
)
def test_normalize_phone_rejected(raw):
    assert normalize_phone(raw) is None
