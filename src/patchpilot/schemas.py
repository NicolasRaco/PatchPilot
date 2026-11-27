"""The two data contracts between pipeline stages.

ISSUE_SCHEMA: Analyzer/Prioritizer -> Context Builder (IF-03).
PATCH_SCHEMA: LLM Client <- model reply, sent as an OpenAI strict structured output (FR-03, IF-04).
Change these only by pull request: every stage depends on them.
"""

ISSUE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Issue",
    "type": "object",
    "properties": {
        # Where the function is
        "id": {"type": "string", "description": "Stable key: '<file>::<function>', plus '@<start_line>' if the name repeats in the file."},
        "file": {"type": "string", "description": "Path relative to the target repo root."},
        "function": {"type": "string", "description": "Qualified name, e.g. 'Cart.total' for a method."},
        "start_line": {"type": "integer", "minimum": 1},
        "end_line": {"type": "integer", "minimum": 1},
        # The measurements
        "cc": {"type": "integer", "minimum": 1, "description": "Cyclomatic complexity (radon)."},
        "sloc": {"type": "integer", "minimum": 1, "description": "Source lines of code in the function."},
        "branch_coverage": {"type": "number", "minimum": 0, "maximum": 1, "description": "Fraction 0-1, not a percent."},
    },
    "required": ["id", "file", "function", "start_line", "end_line", "cc", "sloc", "branch_coverage"],
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
