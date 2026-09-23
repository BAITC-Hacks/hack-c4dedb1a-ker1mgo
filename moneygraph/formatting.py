"""Display formatting shared by the viewer and client fact cards."""


def fmt_kzt(value: float | None) -> str:
    amount = float(value or 0)
    for divisor, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(amount) >= divisor:
            return f"{amount / divisor:.2f}{suffix}"
    return f"{amount:.0f}"
