"""F1 Analyze source: measure every function in a target repo (FR-01).

Output is one issue record per function, matching ISSUE_SCHEMA (IF-03).
Never writes to the target repo (FR-07): coverage data goes to a temp dir,
and pytest's cache and Python's bytecode files are switched off.
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from radon.complexity import cc_visit
from radon.raw import analyze as raw_analyze
from radon.visitors import Class


def analyze(repo) -> list[dict]:
    """Return an issue record for every function and method in the repo's non-test code."""
    repo = Path(repo)
    coverage = measure_coverage(repo)
    issues = []
    for path in sorted(repo.rglob("*.py")):
        rel = path.relative_to(repo).as_posix()
        if _skip(rel):
            continue
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        for block in _functions(cc_visit(source)):
            body = textwrap.dedent("\n".join(lines[block.lineno - 1 : block.endline]))
            issues.append({
                "id": f"{rel}::{block.fullname}",
                "file": rel,
                "function": block.fullname,
                "start_line": block.lineno,
                "end_line": block.endline,
                "cc": block.complexity,
                "sloc": raw_analyze(body).sloc,
                "branch_coverage": _fraction(coverage.get((rel, block.fullname))),
            })
    return issues


def measure_coverage(repo: Path) -> dict:
    """Run the repo's own tests under coverage.py; return {(file, function): summary}."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    with tempfile.TemporaryDirectory() as tmp:
        data, report = Path(tmp, ".coverage"), Path(tmp, "coverage.json")
        tests = subprocess.run(
            [sys.executable, "-m", "coverage", "run", "--branch", "--source=.", f"--data-file={data}",
             "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            cwd=repo, env=env, capture_output=True, text=True,
        )
        # Coverage from a failing suite says nothing about safety, and the Validator needs a green baseline.
        if tests.returncode != 0:
            raise RuntimeError(f"tests do not pass in {repo}:\n{tests.stdout[-2000:]}{tests.stderr[-2000:]}")
        subprocess.run(
            [sys.executable, "-m", "coverage", "json", f"--data-file={data}", "-o", str(report), "-q"],
            cwd=repo, env=env, check=True,
        )
        files = json.loads(report.read_text())["files"]
    return {
        (Path(file).as_posix(), name): region["summary"]
        for file, info in files.items()
        for name, region in info.get("functions", {}).items()
        if name  # "" is the module-level code, not a function
    }


def _fraction(summary) -> float:
    if summary is None:  # file never imported by the tests
        return 0.0
    if summary["num_branches"] == 0:  # no branches (e.g. CC 1): fall back to line coverage
        return summary["percent_covered"] / 100
    return summary["covered_branches"] / summary["num_branches"]


def _functions(blocks):
    # shortcut: nested functions (closures) are skipped; add them if a benchmark repo needs it.
    for block in blocks:
        if isinstance(block, Class):
            yield from block.methods
        else:
            yield block


def _skip(rel: str) -> bool:
    """Test code and hidden/virtualenv folders are not refactoring targets."""
    parts = rel.split("/")
    name = parts[-1]
    return (
        name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"
        or any(p in ("tests", "test", "venv") or p.startswith(".") for p in parts[:-1])
    )
