# PatchPilot

ELEC 490/498 Group 31 capstone. A command-line agent that finds complex Python functions with static analysis, asks a GPT model to refactor them, and keeps a change only if the project's own tests still pass. Full design: Blueprint v2.0 (`03_Blueprint/` in the team drive).

## Setup

Requires Python 3.11+.

```
python -m venv .venv
.venv\Scripts\activate        # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -e .
```

## Tests

```
pytest               # PatchPilot's own tests
pytest sample_repo   # the planted target repo; its baseline must always pass
```

## Layout

| Path | What |
|---|---|
| `src/patchpilot/schemas.py` | The two data contracts: issue record (IF-03) and model patch reply (FR-03). Change only by PR. |
| `sample_repo/` | Target repo with planted issues (M2). `shipping_cost` and `letter_grade` should be selected; `format_report` is complex but untested and must not be (T-02); `clamp` is simple. |
| `tests/` | PatchPilot tests. Name tests after blueprint IDs where possible, e.g. `test_T04_rejects_syntax_error`. |

## Workflow

- Branch from `main`, open a pull request, get one teammate's review, then merge. CI must be green.
- One branch per milestone or requirement, e.g. `p1-prioritizer`, `p2-validator`.
- Never commit API keys. The OpenAI key is read from the `OPENAI_API_KEY` environment variable (NF-04).
