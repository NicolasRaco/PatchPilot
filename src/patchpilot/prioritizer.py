"""F2 Select issues: keep only the functions worth refactoring and safe to refactor (FR-02).

Run on a repo:  python -m patchpilot.prioritizer sample_repo
"""
import json
import sys

from patchpilot.analyzer import analyze

MIN_CC = 11                 # FR-02.1: complex enough to be worth a model call
MIN_BRANCH_COVERAGE = 0.8   # FR-02.2: tested enough that the Validator can catch a broken patch


def select(issues: list[dict]) -> list[dict]:
    """Return the issues to send to the LLM, most complex first."""
    keep = [
        issue
        for issue in issues
        if issue["cc"] >= MIN_CC and issue["branch_coverage"] >= MIN_BRANCH_COVERAGE
    ]
    return sorted(keep, key=lambda issue: issue["cc"], reverse=True)


if __name__ == "__main__":
    print(json.dumps(select(analyze(sys.argv[1])), indent=2))
