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

## Tests

```
pytest               # PatchPilot's own tests
pytest sample_repo   # the planted target repo; its tests must always pass
```

CI runs both on Windows and Ubuntu for every push and pull request.

## Layout

| Path | What |
|---|---|
| `src/patchpilot/schemas.py` | The two data contracts: issue record and model patch reply. Every stage depends on them, so change only by pull request. |
| `sample_repo/` | A small target repo with planted cases for testing the pipeline (see below). It has its own `pytest.ini`. |
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
| FR-02.1 | Select only functions with CC of at least 11, highest first. |
| FR-02.2 | Never select a function unless its tests cover at least 80% of its branches. |
| FR-03 | The LLM Client returns exactly one patch per request, matching the patch schema. |
| IF-01 | For each accepted patch, output one diff and one Markdown report. |
| IF-03 | The Analyzer emits issue records that validate against the issue schema. |
| IF-04 | The LLM Client requests strict JSON replies and validates each one before use. |
| NF-01 | Runs on Python 3.11+ on Windows 11 and Ubuntu 24.04. |
| NF-04 | The API key comes from an environment variable and never appears in logs, reports or prompts. |
| T-01 | Test: the Analyzer finds every function and its CC matches a hand count. |
| T-02 | Test: complex but untested functions are not selected, and the order matches CC. |

## Workflow

- Branch from `main`, open a pull request, get one teammate's review, then merge. CI must be green.
- One branch per piece of work, e.g. `p1-prioritizer`, `p2-validator`.
- Push only when tests pass.
- Never commit API keys. Set `OPENAI_API_KEY` as an environment variable on your machine.
