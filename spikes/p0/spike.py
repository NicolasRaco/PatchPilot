"""
PatchPilot P0: LLM patch spike (throwaway).

For each planted function in targets.json:
  1. send its source to the model, strict JSON output
  2. validate schema + that the code parses
  3. apply to a COPY of the sample repo, run pytest
  4. retry up to MAX_TRIES, feeding the error back
Logs every attempt to p0_results.jsonl and prints a summary.

Setup:
  pip install openai radon pytest jsonschema
  set OPENAI_API_KEY=...            (PowerShell: $env:OPENAI_API_KEY="...")

targets.json example:
  [{"file": "src/sample/utils.py", "function": "parse_config"}]

Run (add --require-drop so no-op patches are rejected and retried):
  python p0_spike.py --repo C:\\path\\to\\sample_repo --targets targets.json --schemas C:\\path\\to\\schemas.py
  python p0_spike.py --repo ... --targets ... --schemas ... --model gpt-5.4-mini --max-tries 3
"""
import argparse, ast, importlib.util, json, shutil, subprocess, sys, tempfile, textwrap, time
from pathlib import Path

import jsonschema
from openai import OpenAI
from radon.complexity import cc_visit

DEFAULT_MODEL = "gpt-5.4-mini"  # confirm exact API model string/version and pin it

def load_patch_schema(path: str) -> dict:
    """Import PATCH_SCHEMA from the team's real schemas file."""
    spec = importlib.util.spec_from_file_location("pp_schemas", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.PATCH_SCHEMA


SYSTEM = (
    "You refactor one Python function to reduce cyclomatic complexity. "
    "Preserve behaviour exactly: same name, signature, return values, exceptions and side effects. "
    "Do not change anything outside the function. Return JSON only: the full replacement "
    "function in new_code (no markdown fences), plus a short explanation of what changed and why."
)


def find_function(src: str, name: str):
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            return start, node.end_lineno, node.col_offset
    raise ValueError(f"function {name} not found")


def get_source(path: Path, name: str):
    src = path.read_text(encoding="utf-8")
    start, end, indent = find_function(src, name)
    lines = src.splitlines()
    snippet = textwrap.dedent("\n".join(lines[start - 1:end]))
    return snippet, start, end, indent


def max_cc(code: str) -> int:
    try:
        return max((b.complexity for b in cc_visit(code)), default=0)
    except Exception:
        return -1


def run_pytest(repo: Path):
    p = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q", "--no-header"],
        cwd=repo, capture_output=True, text=True, timeout=300,
    )
    return p.returncode == 0, (p.stdout + p.stderr)[-3000:]


def apply_patch(repo_copy: Path, rel_file: str, start: int, end: int, indent: int, new_code: str):
    path = repo_copy / rel_file
    lines = path.read_text(encoding="utf-8").splitlines()
    new_block = textwrap.indent(new_code.strip("\n"), " " * indent)
    lines[start - 1:end] = new_block.splitlines()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ask(client, model, messages, use_temp, patch_schema):
    kwargs = dict(model=model, messages=messages,
                  response_format={"type": "json_schema",
                                   "json_schema": {"name": "patch", "strict": True, "schema": patch_schema}})
    if use_temp:
        kwargs["temperature"] = 0
    r = client.chat.completions.create(**kwargs)
    return r.choices[0].message.content, r.usage.prompt_tokens, r.usage.completion_tokens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--targets", required=True)
    ap.add_argument("--schemas", required=True, help="path to the file that defines PATCH_SCHEMA")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--max-tries", type=int, default=3)
    ap.add_argument("--require-drop", action="store_true",
                    help="only accept a patch if CC strictly decreases (no-op patches trigger a retry)")
    ap.add_argument("--temp0", action="store_true", help="send temperature=0 (if the model allows it)")
    ap.add_argument("--out", default="p0_results.jsonl")
    a = ap.parse_args()

    repo = Path(a.repo).resolve()
    targets = json.loads(Path(a.targets).read_text())
    patch_schema = load_patch_schema(a.schemas)
    client = OpenAI()

    ok, out = run_pytest(repo)
    if not ok:
        sys.exit(f"Baseline tests fail on the untouched repo; fix that first.\n{out}")
    print("Baseline green.\n")

    summary = []
    with open(a.out, "a", encoding="utf-8") as log:
        for t in targets:
            snippet, start, end, indent = get_source(repo / t["file"], t["function"])
            cc_before = max_cc(snippet)
            messages = [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"File: {t['file']}\n\n{snippet}"},
            ]
            result = {"function": t["function"], "accepted": False, "tries": 0}
            for attempt in range(1, a.max_tries + 1):
                rec = {"function": t["function"], "attempt": attempt, "model": a.model,
                       "cc_before": cc_before, "schema_valid": False, "parses": False,
                       "tests_pass": False, "cc_after": None}
                t0 = time.time()
                try:
                    raw, tin, tout = ask(client, a.model, messages, a.temp0, patch_schema)
                    rec.update(tokens_in=tin, tokens_out=tout)
                    data = json.loads(raw)
                    jsonschema.validate(data, patch_schema)  # T-03: validate against the real contract
                    rec["schema_valid"] = True
                    rec["explanation"] = data["explanation"]
                    if data["function_name"] != t["function"]:
                        raise ValueError(f"function_name {data['function_name']!r} does not match {t['function']!r}")
                    new_code = data["new_code"]
                    ast.parse(new_code)
                    rec["parses"] = True
                    rec["cc_after"] = max_cc(new_code)

                    with tempfile.TemporaryDirectory() as tmp:
                        copy = Path(tmp) / "repo"
                        shutil.copytree(repo, copy, ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv"))
                        apply_patch(copy, t["file"], start, end, indent, new_code)
                        rec["tests_pass"], test_out = run_pytest(copy)
                    feedback = None if rec["tests_pass"] else f"Tests failed:\n{test_out}"
                except SyntaxError as e:
                    feedback = f"Your code did not parse: {e}"
                except Exception as e:  # schema/API/JSON errors
                    feedback = f"Error: {e}"
                    rec["error"] = str(e)

                if feedback is None:  # tests passed; give the retry a concrete, actionable hint
                    feedback = (f"The tests pass, but complexity is {rec['cc_after']} and must be strictly below "
                                f"{cc_before}. Make a real structural change (lookup table, early returns or guard "
                                "clauses, or extracting a helper function) while keeping behaviour identical.")
                improved = rec["cc_after"] is not None and (
                    rec["cc_after"] < cc_before if a.require_drop else rec["cc_after"] <= cc_before)
                rec["accepted"] = bool(rec["tests_pass"] and improved)
                rec["seconds"] = round(time.time() - t0, 1)
                log.write(json.dumps(rec) + "\n"); log.flush()
                result["tries"] = attempt
                print(f"{t['function']} try {attempt}: schema={rec['schema_valid']} parses={rec['parses']} "
                      f"tests={rec['tests_pass']} cc {cc_before}->{rec['cc_after']}")

                if rec["accepted"]:
                    result.update(accepted=True, cc_after=rec["cc_after"])
                    break
                messages += [
                    {"role": "assistant", "content": raw if rec["schema_valid"] else "{}"},
                    {"role": "user", "content": feedback + "\nReturn a corrected JSON patch."},
                ]
            summary.append(result)

    n = len(summary)
    acc = sum(r["accepted"] for r in summary)
    print(f"\nAccepted {acc}/{n} ({100*acc//max(n,1)}%)")
    for r in summary:
        print(f"  {r['function']}: accepted={r['accepted']} tries={r['tries']}")
    print("Details in", a.out)


if __name__ == "__main__":
    main()