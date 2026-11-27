import hashlib
from pathlib import Path

import pytest
from jsonschema import validate

from patchpilot.analyzer import analyze
from patchpilot.schemas import ISSUE_SCHEMA

SAMPLE = Path(__file__).resolve().parent.parent / "sample_repo"

# Hand counts for the planted cases (see README): (cc, branch_coverage)
EXPECTED = {
    "shipping.py::shipping_cost": (12, 1.0),
    "grades.py::letter_grade": (11, 1.0),
    "report.py::format_report": (11, 0.0),
    "utils.py::clamp": (1, 1.0),
}


def snapshot(repo):
    return {p.relative_to(repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in repo.rglob("*") if p.is_file()}


@pytest.fixture(scope="module")
def run():
    before = snapshot(SAMPLE)
    issues = analyze(SAMPLE)
    return before, issues, snapshot(SAMPLE)


def test_T01_finds_every_function_with_hand_counted_cc(run):
    _, issues, _ = run
    found = {i["id"]: (i["cc"], i["branch_coverage"]) for i in issues}
    assert found == EXPECTED  # test files are not analyzed


def test_IF03_records_match_issue_schema(run):
    _, issues, _ = run
    for issue in issues:
        validate(issue, ISSUE_SCHEMA)


def test_records_locate_the_function(run):
    _, issues, _ = run
    shipping = next(i for i in issues if i["function"] == "shipping_cost")
    assert (shipping["start_line"], shipping["end_line"], shipping["sloc"]) == (1, 25, 25)


def test_FR07_target_repo_untouched(run):
    before, _, after = run
    assert before == after


def test_real_code_shapes_found_on_click(tmp_path):
    # f: radon alone reported end line 2, cutting the call in half. C.m: was listed twice.
    (tmp_path / "mod.py").write_text(
        "def f(a):\n    return max(\n        a,\n        0,\n    )\n\n\n"
        "class C:\n    def m(self):\n        return 1\n"
    )
    (tmp_path / "test_mod.py").write_text("from mod import f\n\ndef test_f():\n    assert f(1) == 1\n")
    f, m = analyze(tmp_path)  # exactly two records: fails if a method is listed twice
    assert (f["id"], m["id"]) == ("mod.py::f", "mod.py::C.m")
    assert (f["end_line"], f["sloc"]) == (5, 5)


@pytest.fixture(scope="module")
def same_names(tmp_path_factory):
    # Found on all 10 benchmark repos: platform variants and property setters share a name.
    repo = tmp_path_factory.mktemp("same_names")
    (repo / "mod.py").write_text(
        "import sys\n"
        "if sys.platform != 'nope':\n"
        "    def f(x):\n        if x:\n            return 1\n        return 2\n"
        "else:\n"
        "    def f(x):\n        if x:\n            return 3\n        return 4\n"
        "\n\nclass C:\n"
        "    @property\n    def v(self):\n        return 1\n\n"
        "    @v.setter\n    def v(self, val):\n        if val:\n            pass\n"
    )
    (repo / "test_mod.py").write_text(
        "from mod import f, C\n\ndef test_f():\n    assert f(1) == 1 and f(0) == 2\n    assert C().v == 1\n"
    )
    return analyze(repo)


def test_FR02_2_same_name_functions_get_their_own_coverage(same_names):
    coverage = [(i["function"], i["start_line"], i["branch_coverage"]) for i in same_names]
    assert coverage == [("f", 3, 1.0), ("f", 8, 0.0), ("C.v", 16, 1.0), ("C.v", 20, 0.0)]


def test_ids_are_unique(same_names):
    ids = [i["id"] for i in same_names]
    assert ids == ["mod.py::f", "mod.py::f@8", "mod.py::C.v", "mod.py::C.v@20"]


def test_failing_suite_is_refused(tmp_path):
    (tmp_path / "test_broken.py").write_text("def test_x():\n    assert False\n")
    with pytest.raises(RuntimeError, match="tests do not pass"):
        analyze(tmp_path)
