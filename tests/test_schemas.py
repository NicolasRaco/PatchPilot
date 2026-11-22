import pytest
from jsonschema import Draft202012Validator, ValidationError, validate

from patchpilot.schemas import ISSUE_SCHEMA, PATCH_SCHEMA

# Real values for sample_repo/shipping.py::shipping_cost, measured with radon and coverage.py.
SHIPPING_ISSUE = {
    "id": "shipping.py::shipping_cost",
    "file": "shipping.py",
    "function": "shipping_cost",
    "start_line": 1,
    "end_line": 25,
    "cc": 12,
    "sloc": 25,
    "branch_coverage": 1.0,
}


def test_schemas_are_valid_json_schema():
    Draft202012Validator.check_schema(ISSUE_SCHEMA)
    Draft202012Validator.check_schema(PATCH_SCHEMA)


def test_patch_schema_meets_openai_strict_mode():
    assert set(PATCH_SCHEMA["required"]) == set(PATCH_SCHEMA["properties"])
    assert PATCH_SCHEMA["additionalProperties"] is False


def test_issue_schema_has_fields():
    assert ISSUE_SCHEMA["properties"], "ISSUE_SCHEMA still has no fields"
    assert set(ISSUE_SCHEMA["required"]) <= set(ISSUE_SCHEMA["properties"])


def test_real_issue_is_accepted():
    validate(SHIPPING_ISSUE, ISSUE_SCHEMA)


@pytest.mark.parametrize(
    "field, bad_value",
    [
        ("cc", 0),                 # complexity is always at least 1
        ("cc", "12"),              # text, not a number
        ("sloc", -5),              # can't have negative lines
        ("branch_coverage", 1.5),  # more than 100% covered is impossible
        ("branch_coverage", -0.1),
    ],
)
def test_broken_issue_is_rejected(field, bad_value):
    with pytest.raises(ValidationError):
        validate({**SHIPPING_ISSUE, field: bad_value}, ISSUE_SCHEMA)
