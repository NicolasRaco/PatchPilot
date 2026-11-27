"""P2 tests: T-04 (bad patches rejected for the right reason) and T-11 (original untouched).

Every case runs in the local sandbox. The same cases run in the docker sandbox too when
the image is built (docker build -t patchpilot-validator:0.1 -f docker/Dockerfile.validator .);
CI builds it on Ubuntu, so there NF-05 is checked inside a real network-less container.
"""
import hashlib
from pathlib import Path

import pytest

from bad_patches import BAD, CORRECT, SAME_CC, reply
from patchpilot import validator as v

SAMPLE = Path(__file__).resolve().parent.parent / "sample_repo"
SHIPPING = {"id": "shipping.py::shipping_cost", "file": "shipping.py",
            "function": "shipping_cost", "start_line": 1}
FAST_TIMEOUT = 5  # FR-09's 60 s floor, shortened so the infinite-loop case finishes quickly

SANDBOXES = [
    "local",
    pytest.param("docker", marks=pytest.mark.skipif(not v.docker_available(),
                                                    reason="docker image not built")),
]


def snapshot(repo):
    return {p.relative_to(repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(repo.rglob("*")) if p.is_file()}


@pytest.fixture(scope="module", params=SANDBOXES)
def baseline(request):
    return v.run_baseline(SAMPLE, sandbox=request.param)


def check(baseline, patch, issue=SHIPPING):
    return v.validate_patch(SAMPLE, issue, patch, baseline=baseline,
                            sandbox=baseline.sandbox, min_timeout=FAST_TIMEOUT)


def test_baseline_sees_every_sample_test(baseline):
    assert len(baseline.passed) == 23  # everything `pytest sample_repo` runs
    assert all("::" in test for test in baseline.passed)


@pytest.mark.parametrize("reason", sorted(BAD))
def test_T04_bad_patch_rejected_for_the_right_reason(baseline, reason):
    verdict = check(baseline, BAD[reason])
    assert (verdict.accepted, verdict.reason) == (False, reason), verdict.detail
    assert verdict.detail, "a rejection must carry error output for the retry (FR-05)"


def test_T04_correct_patch_accepted(baseline):
    verdict = check(baseline, CORRECT)
    assert verdict.accepted, verdict.detail
    assert (verdict.cc_before, verdict.cc_after) == (12, 8)
    assert "_weight_surcharge" in verdict.patched_source  # helper inserted next to the function


def test_FR04_3_equal_cc_is_accepted(baseline):
    verdict = check(baseline, SAME_CC)
    assert verdict.accepted, verdict.detail
    assert verdict.cc_before == verdict.cc_after == 12


def test_FR04_2_detail_names_the_failing_test(baseline):
    verdict = check(baseline, BAD["tests_failed"])
    # local base price 5 -> 6 breaks exactly the four local-zone cases
    assert verdict.newly_failing == [f"tests.test_shipping::test_shipping_cost[{case}]"
                                     for case in ("kwargs0-5.0", "kwargs3-7.5", "kwargs5-8.0", "kwargs7-5.0")]
    assert "test_shipping_cost[kwargs0-5.0]" in verdict.detail


def test_T11_original_repo_untouched(baseline):
    before = snapshot(SAMPLE)
    for patch in [CORRECT, SAME_CC, *BAD.values()]:
        check(baseline, patch)
    assert snapshot(SAMPLE) == before


# ---- applying patches to other code shapes (no tests run, so these are fast)

def test_apply_keeps_decorators_and_method_indent():
    source = ("class Cart:\n"
              "    @staticmethod\n"
              "    def total(items):\n"
              "        return sum(items)\n"
              "\n"
              "    def other(self):\n"
              "        return 1\n")
    issue = {"file": "m.py", "function": "Cart.total", "start_line": 3}
    patched, def_line = v.apply_patch(source, issue, "def total(items):\n    return sum(list(items))\n", "total")
    assert patched == source.replace("return sum(items)", "return sum(list(items))")
    assert def_line == 3


def test_apply_replaces_decorators_when_model_writes_them():
    source = "@cache\ndef f(x):\n    return x\n"
    patched, def_line = v.apply_patch(source, {"start_line": 2}, "@cache\ndef f(x):\n    return x * 1\n", "f")
    assert patched == "@cache\ndef f(x):\n    return x * 1\n"
    assert def_line == 2


def test_apply_picks_the_right_one_of_two_same_named_functions():
    source = "def f(x):\n    return 1\n\n\ndef f(x):\n    return 2\n"
    patched, _ = v.apply_patch(source, {"start_line": 5}, "def f(x):\n    return 3\n", "f")
    assert patched == "def f(x):\n    return 1\n\n\ndef f(x):\n    return 3\n"


def test_schema_invalid_reply_rejected_before_any_work(baseline):
    verdict = check(baseline, {"function_name": "shipping_cost", "new_code": "x"})  # no explanation
    assert verdict.reason == v.INVALID_PATCH


def test_qualified_name_in_reply_is_accepted(baseline):
    assert check(baseline, reply(CORRECT["new_code"], name="shipping.shipping_cost")).accepted
