def late_fee(days_late, balance, tier="standard", prior_late_count=0, grace_days=3):
    """Late fee for an overdue balance; weekly rate steps up the longer it is overdue."""
    if days_late < 0 or balance < 0:
        raise ValueError("negative input")
    if balance == 0:
        return 0.0
    if days_late <= grace_days:
        return 0.0
    fee = 0.0
    overdue = days_late - grace_days
    weeks = 0
    while overdue > 0:
        weeks += 1
        overdue -= 7
        if weeks <= 2:
            fee += balance * 0.01
        elif weeks <= 6:
            fee += balance * 0.02
        else:
            fee += balance * 0.03
    if tier == "gold":
        fee *= 0.5
    elif tier == "silver":
        fee *= 0.75
    if prior_late_count >= 3:
        fee *= 1.25
    cap = balance * 0.10
    if fee > cap:
        fee = cap
    if fee < 5:
        fee = 5.0
    return round(fee, 2)
