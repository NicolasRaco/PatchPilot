# Deliberately untested: complex (CC 11) but 0% branch coverage, so it must NOT be selected (FR-02.2, T-02).
def format_report(rows, sort_by=None, limit=None, show_totals=True):
    if not rows:
        return "(no data)"
    if sort_by is not None:
        if sort_by not in rows[0]:
            raise KeyError(sort_by)
        rows = sorted(rows, key=lambda r: r[sort_by])
    if limit is not None and limit < len(rows):
        rows = rows[:limit]
    lines = []
    total = 0
    for r in rows:
        name = r.get("name") or "?"
        amount = r.get("amount", 0)
        if amount < 0:
            lines.append(f"{name}: ({-amount})")
        elif amount == 0:
            lines.append(f"{name}: -")
        else:
            lines.append(f"{name}: {amount}")
        total += amount
    if show_totals:
        lines.append(f"TOTAL: {total}")
    return "\n".join(lines)
