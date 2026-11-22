def shipping_cost(weight_kg, zone, express=False, member=False, fragile=False):
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
