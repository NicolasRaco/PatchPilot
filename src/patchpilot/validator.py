"""F4 Validate patch: the acceptance gate (FR-04).

Takes one issue record (from the Prioritizer) and one patch reply (from the LLM Client)
and returns a Verdict: accept, or reject with a reason and the error output that goes
back to the model on a retry (FR-05).

Steps, in Blueprint Figure 3 order. Checks stop at the first failure, so a patch that
does not parse never reaches the test runner.

  F4.1 Create isolated copy   the target repo is copied to a temp dir; the original is
                              only ever read (FR-07)
  F4.2 Apply patch            the function's lines in the copy are replaced
  F4.3 Check syntax           the patched module must parse (FR-04.1)
  F4.4 Run tests              pytest in a sandbox with no network (NF-05), outcomes read
                              from the exit code and JUnit XML (IF-05), killed after
                              max(3 x baseline, 60 s) (FR-09); every test that passed
                              before must still pass (FR-04.2)
  F4.5 Re-measure CC          radon on the patched function (FR-04.3)
  F4.6 Decide                 accept only if all of the above hold (FR-04)

Sandboxes:
  "docker"  pytest runs in a container started with --network none (NF-05). Needs the
            image built from docker/Dockerfile.validator.
  "local"   pytest runs as a plain subprocess. For development and Windows CI only.
  "auto"    docker if it is usable, otherwise local (the Verdict says which was used).
In both, a startup hook blocks socket connections, so a patch that calls the network
fails with a clear message instead of hanging.

Try it:  python -m patchpilot.validator sample_repo shipping.py::shipping_cost patch.json
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

from jsonschema import ValidationError, validate as validate_json
from radon.complexity import cc_visit
from radon.visitors import Class

from patchpilot.schemas import PATCH_SCHEMA

DOCKER_IMAGE = "patchpilot-validator:0.1"
MIN_TIMEOUT_S = 60.0        # FR-09: a test run gets max(3 x baseline, 60 s)
TIMEOUT_FACTOR = 3.0
MAX_ERROR_CHARS = 3000      # error output kept for the retry prompt (FR-05)
NETWORK_MARKER = "PatchPilot validator: network access is blocked (NF-05)"

# Folders never copied into the isolated copy: VCS data, caches and virtualenvs.
_IGNORE = shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".venv", "venv",
                                 "*.pyc", ".coverage", "coverage.json", "htmlcov", "runs")

# Loaded by Python at startup (sitecustomize) inside the sandbox. Defence in depth for NF-05:
# the container already has no network; this also covers local mode and gives a clear error.
_NETWORK_GUARD = f'''
import socket

def _blocked(*args, **kwargs):
    raise OSError({NETWORK_MARKER!r})

socket.socket.connect = _blocked
socket.socket.connect_ex = _blocked
socket.create_connection = _blocked
socket.getaddrinfo = _blocked
'''

# Reasons a Verdict can carry. Tests and the Reporter rely on these strings.
ACCEPTED = "accepted"
INVALID_PATCH = "invalid_patch"      # reply does not match PATCH_SCHEMA or names another function
APPLY_FAILED = "apply_failed"        # new_code holds no function with the right name
SYNTAX_ERROR = "syntax_error"        # FR-04.1
TESTS_FAILED = "tests_failed"        # FR-04.2
NETWORK_BLOCKED = "network_blocked"  # NF-05: the patched code tried to open a connection
TIMEOUT = "timeout"                  # FR-09
CC_INCREASED = "cc_increased"        # FR-04.3
SANDBOX_ERROR = "sandbox_error"      # the sandbox itself failed; not the patch's fault


@dataclass
class Verdict:
    accepted: bool
    reason: str
    detail: str = ""                 # error output, sent back to the model on a retry (FR-05)
    cc_before: int | None = None
    cc_after: int | None = None
    newly_failing: list[str] = field(default_factory=list)
    patched_source: str | None = None  # the full patched module, for the Reporter's diff (IF-01)
    sandbox: str = ""
    seconds: float = 0.0

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("patched_source")
        return data


@dataclass
class Baseline:
    """Tests that pass on the untouched repo, and how long the suite takes (FR-04.2, FR-09)."""
    passed: set[str]
    seconds: float
    sandbox: str



# ---------------------------------------------------------------- public API

def run_baseline(repo, sandbox: str = "auto", limit: float = 600.0) -> Baseline:
    """Run the untouched repo's tests once, on a copy, and record which pass and how long they take.

    Run it once per repo and pass the result to every validate_patch call.
    """
    repo = Path(repo)
    mode = _resolve_sandbox(sandbox)
    with tempfile.TemporaryDirectory(prefix="pp-base-") as tmp:
        copy = _copy_repo(repo, Path(tmp))
        run = _run_tests(copy, Path(tmp), mode, timeout=limit)
    if run.timed_out:
        raise RuntimeError(f"baseline tests in {repo} did not finish in {limit:.0f} s")
    if run.error:
        raise RuntimeError(f"baseline tests could not run in {repo}:\n{run.output}")
    return Baseline(passed=run.passed, seconds=run.seconds, sandbox=mode)


def validate_patch(repo, issue: dict, patch: dict, baseline: Baseline | None = None,
                   sandbox: str = "auto", min_timeout: float = MIN_TIMEOUT_S) -> Verdict:
    """F4: accept the patch only if FR-04.1 to FR-04.3 all hold. Never writes to `repo`."""
    started = time.monotonic()
    repo = Path(repo)
    if baseline is None:
        baseline = run_baseline(repo, sandbox)
    mode = baseline.sandbox if sandbox == "auto" else _resolve_sandbox(sandbox)

    def verdict(accepted, reason, detail="", **kw) -> Verdict:
        return Verdict(accepted, reason, _trim(detail), sandbox=mode,
                       seconds=round(time.monotonic() - started, 2), **kw)

    # Reply contract (FR-03, IF-04): checked again here so the gate never trusts its input.
    try:
        validate_json(patch, PATCH_SCHEMA)
    except ValidationError as e:
        return verdict(False, INVALID_PATCH, f"The reply does not match the patch schema: {e.message}")
    target = issue["function"].split(".")[-1]  # 'Cart.total' -> 'total'
    if patch["function_name"].split(".")[-1] != target:
        return verdict(False, INVALID_PATCH,
                       f"function_name is {patch['function_name']!r}, expected {issue['function']!r}.")

    original = (repo / issue["file"]).read_text(encoding="utf-8")
    cc_before = _cc_at(original, issue["start_line"])

    with tempfile.TemporaryDirectory(prefix="pp-val-") as tmp:
        # F4.1 Create isolated copy
        copy = _copy_repo(repo, Path(tmp))

        # F4.2 Apply patch
        try:
            patched, new_def_line = apply_patch(original, issue, patch["new_code"], target)
        except SyntaxError as e:
            return verdict(False, SYNTAX_ERROR, f"Your code does not parse: {_syntax_message(e)}",
                           cc_before=cc_before)
        except ValueError as e:
            return verdict(False, APPLY_FAILED, str(e), cc_before=cc_before)

        # F4.3 Check syntax of the whole patched module (FR-04.1)
        try:
            ast.parse(patched)
        except SyntaxError as e:
            return verdict(False, SYNTAX_ERROR,
                           f"The patched module does not parse: {_syntax_message(e)}", cc_before=cc_before)
        (copy / issue["file"]).write_text(patched, encoding="utf-8")

        # F4.4 Run tests (FR-04.2, FR-09, NF-05, IF-05)
        timeout = max(TIMEOUT_FACTOR * baseline.seconds, min_timeout)
        run = _run_tests(copy, Path(tmp), mode, timeout=timeout)
        if run.timed_out:
            return verdict(False, TIMEOUT,
                           f"The tests did not finish within {run.timeout:.0f} s (FR-09). "
                           "The new code probably loops forever.", cc_before=cc_before)
        if run.error:
            return verdict(False, SANDBOX_ERROR, run.output, cc_before=cc_before)
        newly_failing = sorted(baseline.passed - run.passed)
        if newly_failing:
            reason = NETWORK_BLOCKED if NETWORK_MARKER in run.output else TESTS_FAILED
            head = ("The new code tried to open a network connection, which is not allowed.\n"
                    if reason == NETWORK_BLOCKED else "")
            return verdict(False, reason, head + "Tests that passed before now fail: "
                           + ", ".join(newly_failing) + "\n\n" + run.output,
                           cc_before=cc_before, newly_failing=newly_failing)

    # F4.5 Re-measure CC (FR-04.3)
    cc_after = _cc_at(patched, new_def_line)
    if cc_after > cc_before:
        return verdict(False, CC_INCREASED,
                       f"The tests pass, but cyclomatic complexity rose from {cc_before} to {cc_after}; "
                       "it must not exceed the original.", cc_before=cc_before, cc_after=cc_after)

    # F4.6 Decide
    return verdict(True, ACCEPTED, cc_before=cc_before, cc_after=cc_after, patched_source=patched)


# ---------------------------------------------------------------- F4.2 apply

def apply_patch(source: str, issue: dict, new_code: str, name: str) -> tuple[str, int]:
    """Replace the issue's function in `source` with `new_code`.

    Returns the patched module and the line of the new function's `def`.
    new_code may hold helper functions next to the target; they are inserted with it.
    If new_code has no decorators, the original decorators are kept.
    """
    old = _function_at(ast.parse(source), issue["start_line"])
    new_code = textwrap.dedent(new_code).strip("\n")
    new_tree = ast.parse(new_code)  # SyntaxError goes to the caller (FR-04.1)
    defs = [n for n in new_tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    matches = [n for n in defs if n.name == name]
    if len(matches) != 1:
        raise ValueError(f"new_code must define the function {name!r} exactly once; "
                         f"it defines {[n.name for n in defs] or 'no functions'}.")
    new_fn = matches[0]

    lines = source.splitlines()
    first = min([old.lineno] + [d.lineno for d in old.decorator_list])
    # Replace the decorators too only if the model wrote its own; otherwise keep them.
    start = first if new_fn.decorator_list else old.lineno
    indent = " " * old.col_offset
    block = textwrap.indent(new_code, indent, lambda line: True).splitlines()
    block = [line if line.strip() else "" for line in block]
    lines[start - 1 : old.end_lineno] = block
    patched = "\n".join(lines) + ("\n" if source.endswith("\n") else "")
    new_def_line = start + new_fn.lineno - 1
    return patched, new_def_line


def _function_at(tree: ast.AST, line: int) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.lineno == line:
            return node
    raise ValueError(f"no function starts on line {line}; the issue record is out of date.")


def _trim(text: str, head: int = 600) -> str:
    """Keep the summary at the top and the end of the pytest output, where the errors are."""
    if len(text) <= MAX_ERROR_CHARS:
        return text
    return text[:head] + "\n[...]\n" + text[-(MAX_ERROR_CHARS - head):]


def _syntax_message(e: SyntaxError) -> str:
    return f"{e.msg} (line {e.lineno})" + (f": {e.text.strip()}" if e.text else "")


# ---------------------------------------------------------------- F4.5 measure

def _cc_at(source: str, def_line: int) -> int:
    """Cyclomatic complexity (radon) of the function whose `def` is on def_line."""
    # radon lists methods as their own blocks after their class, so classes are skipped.
    for block in cc_visit(source):
        if not isinstance(block, Class) and block.lineno == def_line:
            return block.complexity
    raise ValueError(f"radon found no function on line {def_line}")


# ---------------------------------------------------------------- F4.1 copy

def _copy_repo(repo: Path, tmp: Path) -> Path:
    copy = tmp / "repo"
    shutil.copytree(repo, copy, ignore=_IGNORE)
    return copy


# ---------------------------------------------------------------- F4.4 run tests

@dataclass
class _TestRun:
    passed: set[str]
    output: str
    seconds: float
    timeout: float
    timed_out: bool = False
    error: bool = False


def _run_tests(copy: Path, tmp: Path, mode: str, timeout: float) -> _TestRun:
    """Run pytest on the copy in the sandbox; read outcomes from JUnit XML (IF-05)."""
    out_dir = tmp / "out"
    guard_dir = tmp / "guard"
    out_dir.mkdir(exist_ok=True)
    guard_dir.mkdir(exist_ok=True)
    (guard_dir / "sitecustomize.py").write_text(_NETWORK_GUARD, encoding="utf-8")
    report = out_dir / "junit.xml"
    if report.exists():
        report.unlink()

    pytest_args = ["-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "junit_family=xunit2"]
    name = f"pp-validate-{uuid.uuid4().hex[:12]}"
    if mode == "docker":
        user = [] if os.name == "nt" else ["--user", f"{os.getuid()}:{os.getgid()}"]
        cmd = ["docker", "run", "--rm", "--name", name, "--network", "none",
               "--memory", "1g", "--pids-limit", "256", *user,
               "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "PYTHONPATH=/guard", "-e", "HOME=/tmp",
               "-v", f"{copy}:/work", "-v", f"{guard_dir}:/guard:ro", "-v", f"{out_dir}:/out",
               "-w", "/work", DOCKER_IMAGE, "python", *pytest_args, "--junitxml=/out/junit.xml"]
        env = None
    else:
        cmd = [sys.executable, *pytest_args, f"--junitxml={report}"]
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONPATH": os.pathsep.join([str(guard_dir), os.environ.get("PYTHONPATH", "")]).rstrip(os.pathsep)}

    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=copy, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as e:
        if mode == "docker":
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        output = _text(e.stdout) + _text(e.stderr)
        return _TestRun(set(), output, time.monotonic() - started, timeout, timed_out=True)
    seconds = time.monotonic() - started
    output = proc.stdout + proc.stderr

    # pytest exit codes: 0 all passed, 1 some failed, 5 no tests collected. Anything else means
    # pytest itself could not run (bad usage, internal error) or, for docker, 125 to 127.
    if proc.returncode not in (0, 1, 5) and not report.exists():
        return _TestRun(set(), output, seconds, timeout, error=True)
    return _TestRun(_passed_tests(report), output, seconds, timeout)


def _passed_tests(report: Path) -> set[str]:
    """Test ids that passed, from pytest's JUnit XML. A missing report means nothing passed."""
    if not report.exists():
        return set()
    passed = set()
    for case in ET.parse(report).getroot().iter("testcase"):
        if any(child.tag in ("failure", "error", "skipped") for child in case):
            continue
        passed.add(f"{case.get('classname')}::{case.get('name')}")
    return passed


def _text(data) -> str:
    if data is None:
        return ""
    return data.decode("utf-8", "replace") if isinstance(data, bytes) else data


# ---------------------------------------------------------------- sandbox choice

def docker_available() -> bool:
    """True if the docker daemon answers and the validator image exists."""
    if shutil.which("docker") is None:
        return False
    try:
        probe = subprocess.run(["docker", "image", "inspect", DOCKER_IMAGE],
                               capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0


def _resolve_sandbox(sandbox: str) -> str:
    if sandbox == "auto":
        return "docker" if docker_available() else "local"
    if sandbox == "docker" and not docker_available():
        raise RuntimeError(f"docker sandbox requested but docker or the image {DOCKER_IMAGE} is not "
                           "available. Build it: docker build -t "
                           f"{DOCKER_IMAGE} -f docker/Dockerfile.validator .")
    if sandbox not in ("docker", "local"):
        raise ValueError(f"unknown sandbox {sandbox!r}: use auto, docker or local")
    return sandbox


# ---------------------------------------------------------------- command line

def locate(repo: Path, issue_id: str) -> dict:
    """Minimal issue record (file, function, start_line) from an id like 'shipping.py::shipping_cost'."""
    file, _, name = issue_id.partition("::")
    name, _, at = name.partition("@")
    source = (repo / file).read_text(encoding="utf-8")
    for block in cc_visit(source):
        if not isinstance(block, Class) and block.fullname == name and (not at or block.lineno == int(at)):
            return {"id": issue_id, "file": file, "function": name, "start_line": block.lineno}
    raise SystemExit(f"function {issue_id} not found")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Validate one patch reply against a target repo (F4).")
    ap.add_argument("repo")
    ap.add_argument("issue_id", help="e.g. shipping.py::shipping_cost")
    ap.add_argument("patch", help="JSON file with function_name, new_code, explanation")
    ap.add_argument("--sandbox", choices=["auto", "docker", "local"], default="auto")
    a = ap.parse_args(argv)
    repo = Path(a.repo)
    result = validate_patch(repo, locate(repo, a.issue_id),
                            json.loads(Path(a.patch).read_text(encoding="utf-8")), sandbox=a.sandbox)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
