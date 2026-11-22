"""Guards the planted issues in sample_repo/ so edits can't silently break T-01/T-02."""
from pathlib import Path

import pytest
from radon.complexity import cc_visit

SAMPLE = Path(__file__).resolve().parent.parent / "sample_repo"


def cc_of(module, function):
    blocks = cc_visit((SAMPLE / module).read_text())
    return next(b.complexity for b in blocks if b.name == function)


@pytest.mark.parametrize(
    "module, function, expected_cc",
    [
        ("shipping.py", "shipping_cost", 12),  # tested, should be selected
        ("grades.py", "letter_grade", 11),     # tested, exactly on the FR-02.1 threshold
        ("report.py", "format_report", 11),    # untested, must NOT be selected (FR-02.2)
        ("utils.py", "clamp", 1),              # simple, never selected
    ],
)
def test_planted_complexity(module, function, expected_cc):
    assert cc_of(module, function) == expected_cc
