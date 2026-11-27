def parse_duration(text):
    """Parse strings like '1h 30m', '90s', '-2d' into seconds."""
    if text is None:
        raise ValueError("no duration")
    text = text.strip().lower()
    if not text:
        raise ValueError("empty duration")
    negative = text.startswith("-")
    if negative:
        text = text[1:]
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    total = 0
    number = ""
    seen = set()
    for ch in text:
        if ch.isdigit():
            number += ch
        elif ch in units:
            if not number:
                raise ValueError("unit without number")
            if ch in seen:
                raise ValueError("repeated unit")
            seen.add(ch)
            total += int(number) * units[ch]
            number = ""
        elif ch == " ":
            continue
        else:
            raise ValueError("bad character")
    if number:
        raise ValueError("number without unit")
    return -total if negative else total


def normalize_phone(raw, default_country="1"):
    """Return '+<digits>' or None if the number is not usable."""
    if raw is None:
        return None
    digits = ""
    plus = False
    for i, ch in enumerate(raw.strip()):
        if ch == "+" and i == 0:
            plus = True
        elif ch.isdigit():
            digits += ch
        elif ch in " -().":
            continue
        else:
            return None
    if not digits:
        return None
    if plus:
        pass
    elif len(digits) == 10:
        digits = default_country + digits
    elif len(digits) == 11 and digits.startswith(default_country):
        pass
    else:
        return None
    if len(digits) < 11 or len(digits) > 15:
        return None
    return "+" + digits
