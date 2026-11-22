"""The two data contracts between pipeline stages.

ISSUE_SCHEMA: Analyzer/Prioritizer -> Context Builder (IF-03).
PATCH_SCHEMA: LLM Client <- model reply, sent as an OpenAI strict structured output (FR-03, IF-04).
Change these only by pull request: every stage depends on them.
"""

ISSUE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Issue",
    "type": "object",
    # TODO(human): define "properties" and "required" for one issue record.
    "properties": {},
    "required": [],
    "additionalProperties": False,
}

# OpenAI strict mode requires every property listed in "required" and additionalProperties false.
PATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "function_name": {
            "type": "string",
            "description": "Name of the function being replaced; must match the issue.",
        },
        "new_code": {
            "type": "string",
            "description": "Complete source of the refactored function, same signature, no surrounding code.",
        },
        "explanation": {
            "type": "string",
            "description": "One or two sentences on what was changed and why, for the report (IF-01).",
        },
    },
    "required": ["function_name", "new_code", "explanation"],
    "additionalProperties": False,
}
