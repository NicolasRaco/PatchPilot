def parse_log_line(line):
    """Return (level, message) or None for blank input."""
    if line is None or not line.strip():
        return None
    line = line.strip()
    if line.startswith("#"):
        return ("comment", line[1:].strip())
    parts = line.split(" ", 2)
    if len(parts) < 2:
        return ("text", line)
    level = parts[0].upper().strip("[]:")
    if level in ("ERR", "ERROR", "FATAL"):
        level = "error"
    elif level in ("WARN", "WARNING"):
        level = "warning"
    elif level == "INFO":
        level = "info"
    elif level == "DEBUG":
        level = "debug"
    else:
        return ("text", line)
    message = parts[1] if len(parts) == 2 else parts[1] + " " + parts[2]
    if level == "error" and "timeout" in message.lower():
        level = "timeout"
    return (level, message)
