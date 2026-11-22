def letter_grade(scores, late_penalty=0.0, curve=0.0):
    if not scores:
        raise ValueError("no scores")
    if late_penalty < 0:
        raise ValueError("late_penalty must not be negative")
    total = 0.0
    for s in scores:
        if s < 0 or s > 100:
            raise ValueError(f"score out of range: {s}")
        total += s
    avg = total / len(scores) - late_penalty + curve
    if avg >= 90:
        return "A+" if avg >= 97 else "A"
    elif avg >= 80:
        return "B"
    elif avg >= 70:
        return "C"
    elif avg >= 60:
        return "D"
    return "F"
