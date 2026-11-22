from jsonschema import Draft202012Validator

from patchpilot.schemas import ISSUE_SCHEMA, PATCH_SCHEMA


def test_schemas_are_valid_json_schema():
    Draft202012Validator.check_schema(ISSUE_SCHEMA)
    Draft202012Validator.check_schema(PATCH_SCHEMA)


def test_patch_schema_meets_openai_strict_mode():
    assert set(PATCH_SCHEMA["required"]) == set(PATCH_SCHEMA["properties"])
    assert PATCH_SCHEMA["additionalProperties"] is False


def test_issue_schema_has_fields():
    assert ISSUE_SCHEMA["properties"], "ISSUE_SCHEMA still has no fields"
    assert set(ISSUE_SCHEMA["required"]) <= set(ISSUE_SCHEMA["properties"])
