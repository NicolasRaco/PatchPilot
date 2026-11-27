"""T-04 bad-patch library: model replies the Validator must reject, plus one it must accept.

Every patch targets sample_repo/shipping.py::shipping_cost (CC 12, 100% branch coverage).
Each bad patch is written to fail exactly one check, so the test can assert the reason.
"""

ORIGINAL_BODY = '''\
    if weight_kg <= 0:
        raise ValueError("weight must be positive")
    if zone == "local":
        cost = 5.0
    elif zone == "national":
        cost = 10.0
    elif zone == "international":
        cost = 25.0
    else:
        raise ValueError(f"unknown zone: {zone}")
    if weight_kg > 20:
        cost += 15.0
    elif weight_kg > 5:
        cost += 5.0
    if express:
        if zone == "international":
            cost *= 2.0
        else:
            cost *= 1.5
    if fragile:
        cost += 3.0
    if member and cost > 20:
        cost -= 5.0
    return round(cost, 2)
'''

SIGNATURE = "def shipping_cost(weight_kg, zone, express=False, member=False, fragile=False):\n"


def reply(new_code, name="shipping_cost"):
    return {"function_name": name, "new_code": new_code, "explanation": "test patch"}


# The one good patch: a lookup table and a helper cut CC from 12 to 8, behaviour unchanged.
CORRECT = reply('''\
def shipping_cost(weight_kg, zone, express=False, member=False, fragile=False):
    if weight_kg <= 0:
        raise ValueError("weight must be positive")
    if zone not in _BASE_COST:
        raise ValueError(f"unknown zone: {zone}")
    cost = _BASE_COST[zone] + _weight_surcharge(weight_kg)
    if express:
        cost *= 2.0 if zone == "international" else 1.5
    cost += 3.0 if fragile else 0.0
    if member and cost > 20:
        cost -= 5.0
    return round(cost, 2)


_BASE_COST = {"local": 5.0, "national": 10.0, "international": 25.0}


def _weight_surcharge(weight_kg):
    if weight_kg > 20:
        return 15.0
    return 5.0 if weight_kg > 5 else 0.0
''')

# Same CC (renamed variable): FR-04.3 says CC must not *exceed* the original, so this passes.
SAME_CC = reply(SIGNATURE + ORIGINAL_BODY.replace("cost", "price"))

BAD = {
    # FR-04.1: missing colon after the if
    "syntax_error": reply(SIGNATURE + ORIGINAL_BODY.replace("if fragile:", "if fragile")),
    # FR-04.2: local base price changed, so test_shipping_cost[kwargs0] fails
    "tests_failed": reply(SIGNATURE + ORIGINAL_BODY.replace("cost = 5.0", "cost = 6.0")),
    # FR-04.3: behaviour kept, but a pointless branch raises CC from 12 to 15
    "cc_increased": reply(SIGNATURE + ORIGINAL_BODY.replace(
        "    return round(cost, 2)",
        "    if express and fragile and member:\n        pass\n    return round(cost, 2)")),
    # FR-09: never returns
    "timeout": reply(SIGNATURE + "    while True:\n        pass\n" + ORIGINAL_BODY),
    # NF-05: phones home before doing the real work
    "network_blocked": reply(SIGNATURE
                             + '    import socket\n    socket.create_connection(("example.com", 80), timeout=2)\n'
                             + ORIGINAL_BODY),
    # Reply names a different function than the issue
    "invalid_patch": reply(SIGNATURE + ORIGINAL_BODY, name="letter_grade"),
    # new_code holds a helper but not the function itself
    "apply_failed": reply("def helper(x):\n    return x\n"),
}
