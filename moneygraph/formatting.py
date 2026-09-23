"""Display formatting shared by the viewer and client fact cards."""


def fmt_kzt(value: float | None, *, locale: str = "en") -> str:
    amount = float(value or 0)
    units = (
        ((1e9, " млрд"), (1e6, " млн"), (1e3, " тыс."))
        if locale == "ru"
        else ((1e9, "B"), (1e6, "M"), (1e3, "k"))
    )
    for divisor, suffix in units:
        if abs(amount) >= divisor:
            text = f"{amount / divisor:.2f}{suffix}"
            return text.replace(".", ",", 1) if locale == "ru" else text
    text = f"{amount:,.0f}"
    return text.replace(",", " ") if locale == "ru" else text
