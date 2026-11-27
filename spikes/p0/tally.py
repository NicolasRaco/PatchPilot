"""Summarise one or more P0 result files (.jsonl) as a single experiment.

Usage:
    python tally.py spikes/p0/try1.jsonl [more files...]

Reports two notions of success side by side:
    loose  = tests pass and CC did not increase
    strict = tests pass and CC strictly decreased

Saves the report next to the first .jsonl file, named after the input file(s):
    try1.jsonl                  -> try1_report.txt
    try1.jsonl try1b.jsonl      -> try1_try1b_report.txt
"""

import json
import sys
from collections import defaultdict
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from statistics import mean


if len(sys.argv) < 2:
    print("Usage: python tally.py <results.jsonl> [more.jsonl ...]")
    sys.exit(1)

paths = [Path(p) for p in sys.argv[1:]]

recs = []

for path in paths:
    with open(path, encoding="utf-8") as f:
        recs += [
            json.loads(line)
            for line in f
            if line.strip()
        ]

if not recs:
    print("No experiment records found. Provide at least one JSONL file.")
    sys.exit(1)


by_fn = defaultdict(list)

for r in recs:
    by_fn[r["function"]].append(r)

for rs in by_fn.values():
    rs.sort(key=lambda r: r["attempt"])


def loose(r):
    return (
        r["tests_pass"]
        and r["cc_after"] is not None
        and r["cc_after"] <= r["cc_before"]
    )


def strict(r):
    return (
        r["tests_pass"]
        and r["cc_after"] is not None
        and r["cc_after"] < r["cc_before"]
    )


def generate_report():
    n = len(by_fn)

    print(f"Input file(s): {', '.join(p.name for p in paths)}")
    print(f"Functions: {n}   Attempts: {len(recs)}")

    print(
        f"Schema-valid replies (T-03, target 100%): "
        f"{sum(r['schema_valid'] for r in recs)}/{len(recs)}"
    )

    hit_loose = {
        fn: next((r for r in rs if loose(r)), None)
        for fn, rs in by_fn.items()
    }

    hit_strict = {
        fn: next((r for r in rs if strict(r)), None)
        for fn, rs in by_fn.items()
    }

    nl = sum(1 for h in hit_loose.values() if h)
    ns = sum(1 for h in hit_strict.values() if h)

    print(
        f"Loose  (CC not increased): {nl}/{n} "
        f"({100 * nl // max(n, 1)}%)"
    )

    print(
        f"Strict (CC reduced):       {ns}/{n} "
        f"({100 * ns // max(n, 1)}%)"
    )

    for k in (1, 2, 3):
        c = sum(
            1 for h in hit_strict.values()
            if h and h["attempt"] <= k
        )
        print(f"  strict within {k} attempt(s): {c}/{n}")

    drops = [
        (
            (h["cc_before"] - h["cc_after"]) / h["cc_before"]
            if h["cc_before"] != 0 else 0.0
        )
        if h else 0.0
        for h in hit_strict.values()
    ]

    real = [d for d in drops if d > 0]

    if real:
        print(
            f"Mean CC drop, improved functions only: "
            f"{100 * mean(real):.0f}%"
        )

    print(
        f"Mean CC drop, all functions (failures = 0): "
        f"{100 * mean(drops):.0f}% "
        f"(PF-02 target 30%, min 20%)"
    )

    tin = [
        r["tokens_in"]
        for r in recs
        if "tokens_in" in r
    ]

    tout = [
        r["tokens_out"]
        for r in recs
        if "tokens_out" in r
    ]

    if tin:
        print(
            f"Avg tokens per attempt: "
            f"{mean(tin):.0f} in / {mean(tout):.0f} out "
            f"(Blueprint est. 4000 / 1000)"
        )

    print(
        f"Avg seconds per attempt: "
        f"{mean(r['seconds'] for r in recs):.1f}"
    )

    fails = defaultdict(int)

    for r in recs:
        if strict(r):
            continue

        if not r["schema_valid"]:
            fails["schema/API error"] += 1
        elif not r["parses"]:
            fails["did not parse"] += 1
        elif not r["tests_pass"]:
            fails["tests failed"] += 1
        elif r["cc_after"] == r["cc_before"]:
            fails["no-op (CC unchanged)"] += 1
        else:
            fails["CC increased"] += 1

    if fails:
        print(
            "Attempts that were not a strict improvement:",
            dict(fails)
        )


if __name__ == "__main__":
    # Generate the report in memory first.
    report = StringIO()
    with redirect_stdout(report):
        generate_report()

    report_text = report.getvalue()

    # Display it in the terminal.
    print(report_text, end="")

    # Name the report after the input file(s), and save it beside the first one.
    report_name = "_".join(p.stem for p in paths) + "_report.txt"
    report_path = paths[0].parent / report_name

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    print(f"\nReport saved to {report_path}")