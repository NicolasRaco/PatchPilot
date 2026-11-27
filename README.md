# PatchPilot

ELEC 490/498 Group 31 capstone. A command-line agent that finds complex Python functions with static analysis, asks a GPT model to refactor them, and keeps a change only if the project's own tests still pass. The original repository is never modified; each accepted change is returned as a diff with a short report.

## How it works

Five stages, run in order on a target repository:

1. **Analyzer** measures every function: complexity, size, test coverage.
2. **Prioritizer** picks the functions worth refactoring and writes one *issue record* per function.
3. **Context Builder + LLM Client** send the function to GPT and get back one *patch*.
4. **Validator** runs the patch on an isolated copy of the repo. It is kept only if the code parses, every previously passing test still passes, and complexity did not go up. A rejected patch's error goes back to GPT for a retry.
5. **Reporter** writes a diff and a Markdown report for each accepted patch.

The issue record and the patch are the only data passed between stages. Both are defined in `src/patchpilot/schemas.py`.

## Setup

Requires Python 3.11 or later (`python --version` to check).

```
git clone https://github.com/NicolasRaco/PatchPilot.git
cd PatchPilot
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -e .
```

If `python` points to an older version on Windows, use `py -3.12 -m venv .venv` instead.

## Validator sandbox (P2)

The Validator runs patched code in a Docker container with no network (NF-05). Build the image once:

```
docker build -t patchpilot-validator:0.1 -f docker/Dockerfile.validator docker
```

Without the image, the Validator falls back to running pytest as a normal subprocess (`sandbox="local"`) and says so in its result. Both modes block socket connections, but only the container is a real sandbox, so use local mode for development only. On Windows, Docker Desktop must be running.

Rejection reasons: `invalid_patch`, `apply_failed`, `syntax_error` (FR-04.1), `tests_failed` (FR-04.2), `network_blocked` (NF-05), `timeout` (FR-09), `cc_increased` (FR-04.3), `sandbox_error`.

## Tests

```
pytest               # PatchPilot's own tests
pytest sample_repo   # the planted target repo; its tests must always pass
```

CI runs both on Windows and Ubuntu for every push and pull request. A second CI job builds the validator image and re-runs `tests/test_validator.py` inside the container; locally those container cases are skipped unless the image is built.

## Layout

| Path | What |
|---|---|
| `src/patchpilot/schemas.py` | The two data contracts: issue record and model patch reply. Every stage depends on them, so change only by pull request. |
| `src/patchpilot/analyzer.py` | Analyzer: runs the target's tests under coverage.py and measures every function with radon. One issue record per function. |
| `src/patchpilot/prioritizer.py` | Prioritizer: keeps the issues that meet FR-02. Try it: `python -m patchpilot.prioritizer sample_repo` |
| `src/patchpilot/validator.py` | Validator (F4): applies one patch to an isolated copy, runs the tests with no network, re-measures CC, and returns accept or reject with a reason. Try it: `python -m patchpilot.validator sample_repo shipping.py::shipping_cost patch.json` |
| `docker/Dockerfile.validator` | The container the Validator runs patched code in (NF-05). |
| `sample_repo/` | A small target repo with planted cases for testing the pipeline (see below). It has its own `pytest.ini`. |
| `tests/bad_patches.py` | T-04 bad-patch library: syntax error, broken test, higher CC, infinite loop, network call, plus one correct patch. |
| `tests/` | PatchPilot's tests. Name tests after requirement IDs where possible, e.g. `test_T04_rejects_syntax_error`. |

### Planted cases in `sample_repo/`

| Function | Complexity | Tested? | Expected |
|---|---|---|---|
| `shipping_cost` | 12 | yes, 100% of branches | selected |
| `letter_grade` | 11 (exactly on the threshold) | yes, 100% of branches | selected |
| `format_report` | 11 | no | **not** selected: too risky without tests |
| `clamp` | 1 | yes | not selected: already simple |

`tests/test_sample_repo.py` fails if anyone edits these and changes their complexity.

## Terms

- **CC (cyclomatic complexity):** the number of paths through a function. Starts at 1, plus 1 for each `if`, `elif`, `for`, `while`, `and`, `or`, `except`. Measured with [radon](https://radon.readthedocs.io/).
- **SLOC:** source lines of code, not counting blank lines or comments.
- **Branch coverage:** the fraction (0 to 1) of a function's branches that the tests execute. Measured with [coverage.py](https://coverage.readthedocs.io/).

## Requirement IDs used in the code

The IDs come from the team's design document (the project Blueprint). Only the ones referenced in this repo are listed.

| ID | Meaning |
|---|---|
| FR-01 | The Analyzer measures complexity and test coverage for every function. |
| FR-02.1 | Select only functions with CC of at least 11, highest first. |
| FR-02.2 | Never select a function unless its tests cover at least 80% of its branches. |
| FR-03 | The LLM Client returns exactly one patch per request, matching the patch schema. |
| FR-04 | The Validator accepts a patch only if FR-04.1 to FR-04.3 all hold. |
| FR-04.1 | The patched module parses as valid Python. |
| FR-04.2 | Every test that passed before the patch still passes. |
| FR-04.3 | The patched function's CC does not exceed its original CC. |
| FR-05 | On rejection, the error output goes back to the model, up to the retry limit. |
| FR-07 | The agent never writes to the original repository. |
| FR-09 | A test run longer than max(3 x baseline, 60 s) is killed and the patch rejected. |
| IF-01 | For each accepted patch, output one diff and one Markdown report. |
| IF-03 | The Analyzer emits issue records that validate against the issue schema. |
| IF-04 | The LLM Client requests strict JSON replies and validates each one before use. |
| IF-05 | The Validator reads test outcomes from pytest's exit code and JUnit XML report. |
| NF-01 | Runs on Python 3.11+ on Windows 11 and Ubuntu 24.04. |
| NF-04 | The API key comes from an environment variable and never appears in logs, reports or prompts. |
| NF-05 | Patched code runs in a container with no network access. |
| T-01 | Test: the Analyzer finds every function and its CC matches a hand count. |
| T-02 | Test: complex but untested functions are not selected, and the order matches CC. |
| T-04 | Test: every planted bad patch is rejected for the right reason; a correct patch is accepted. |
| T-11 | Test: every file of the original repo has the same hash before and after a run. |

## Workflow

- Branch from `main`, open a pull request, get one teammate's review, then merge. CI must be green.
- One branch per piece of work, e.g. `p1-prioritizer`, `p2-validator`.
- Push only when tests pass.
- Never commit API keys. Set `OPENAI_API_KEY` as an environment variable on your machine.
