import pytest

from logs import parse_log_line


@pytest.mark.parametrize("line", [None, "", "   "])
def test_blank_lines(line):
    assert parse_log_line(line) is None


@pytest.mark.parametrize(
    "line, expected",
    [
        ("# hello there", ("comment", "hello there")),
        ("singleword", ("text", "singleword")),
        ("hello world", ("text", "hello world")),
        ("ERROR disk full", ("error", "disk full")),
        ("ERR bad", ("error", "bad")),
        ("[WARN] low memory", ("warning", "low memory")),
        ("WARNING x", ("warning", "x")),
        ("INFO: started", ("info", "started")),
        ("debug x", ("debug", "x")),
        ("FATAL Connection TIMEOUT reached", ("timeout", "Connection TIMEOUT reached")),
    ],
)
def test_parse_log_line(line, expected):
    assert parse_log_line(line) == expected
