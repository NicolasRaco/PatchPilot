import pytest

from grades import letter_grade


@pytest.mark.parametrize(
    "scores, kwargs, expected",
    [
        ([98], {}, "A+"),
        ([92], {}, "A"),
        ([85], {}, "B"),
        ([75], {}, "C"),
        ([65], {}, "D"),
        ([10], {}, "F"),
        ([85], dict(late_penalty=10), "C"),
        ([85], dict(curve=10), "A"),
    ],
)
def test_letter_grade(scores, kwargs, expected):
    assert letter_grade(scores, **kwargs) == expected


@pytest.mark.parametrize("scores, kwargs", [([], {}), ([101], {}), ([-1], {}), ([50], dict(late_penalty=-1))])
def test_letter_grade_rejects_bad_input(scores, kwargs):
    with pytest.raises(ValueError):
        letter_grade(scores, **kwargs)
