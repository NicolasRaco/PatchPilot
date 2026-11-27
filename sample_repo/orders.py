def order_total(items, customer_type="regular", coupon=None, shipping_zone="local"):
    """Final price for a list of (unit_price, qty) items."""
    if not items:
        raise ValueError("empty order")
    subtotal = 0
    count = 0
    for price, qty in items:
        if price < 0 or qty <= 0:
            raise ValueError("bad item")
        subtotal += price * qty
        count += qty
    if customer_type == "vip":
        rate = 0.15
    elif customer_type == "member":
        rate = 0.10
    elif customer_type == "regular":
        rate = 0.0
    else:
        raise ValueError("unknown customer type")
    if count >= 10:
        rate += 0.05
    if coupon == "SAVE5":
        subtotal -= 5
    elif coupon == "HALF" and subtotal > 100:
        rate += 0.5
    elif coupon is not None:
        raise ValueError("bad coupon")
    total = subtotal * (1 - min(rate, 0.6))
    if shipping_zone == "local":
        total += 5
    elif shipping_zone == "remote":
        total += 20
    if total < 0:
        total = 0
    return round(total, 2)


def validate_order(order):
    """Return a list of error strings (empty list means valid)."""
    if not isinstance(order, dict):
        return ["order must be a dict"]
    errors = []
    if not order.get("id"):
        errors.append("missing id")
    email = order.get("email", "")
    if "@" not in email:
        errors.append("bad email")
    elif email.startswith("@") or email.endswith("@"):
        errors.append("bad email")
    items = order.get("items")
    if not items:
        errors.append("no items")
    else:
        for i, item in enumerate(items):
            if "sku" not in item:
                errors.append(f"item {i}: missing sku")
            qty = item.get("qty", 0)
            if not isinstance(qty, int) or qty <= 0:
                errors.append(f"item {i}: bad qty")
            elif qty > 100:
                errors.append(f"item {i}: qty too large")
    if order.get("express") and order.get("country") != "US":
        errors.append("express only in US")
    return errors
