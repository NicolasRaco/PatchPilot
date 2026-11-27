from pathlib import Path

from patchpilot.analyzer import analyze
from patchpilot.prioritizer import select

SAMPLE = Path(__file__).resolve().parent.parent / "sample_repo"


def issue(name, cc, coverage):
    return {"id": f"m.py::{name}", "file": "m.py", "function": name, "start_line": 1,
            "end_line": 2, "cc": cc, "sloc": 2, "branch_coverage": coverage}


def test_T02_sample_repo_selection():
    ids = [i["id"] for i in select(analyze(SAMPLE))]
    assert ids == ["shipping.py::shipping_cost", "grades.py::letter_grade"]


def test_FR02_thresholds_are_inclusive():
    picked = select([issue("on_both_lines", 11, 0.8)])
    assert [i["function"] for i in picked] == ["on_both_lines"]


def test_FR02_rejects_below_either_threshold():
    assert select([issue("too_simple", 10, 1.0), issue("too_risky", 30, 0.79)]) == []


def test_FR02_1_most_complex_first():
    picked = select([issue("mid", 15, 0.9), issue("high", 40, 0.9), issue("low", 11, 0.9)])
    assert [i["function"] for i in picked] == ["high", "mid", "low"]
