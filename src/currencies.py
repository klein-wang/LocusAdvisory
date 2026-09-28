from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class Currency:
    code: str
    symbol: str
    label: str

CURRENCIES: Dict[str, Currency] = {
    "HKD": Currency(code="HKD", symbol="HK$", label="Hong Kong Dollar"),
    "USD": Currency(code="USD", symbol="$", label="US Dollar"),
    "RMB": Currency(code="RMB", symbol="¥", label="Chinese Yuan"),
    "EUR": Currency(code="EUR", symbol="€", label="Euro"),
    "GBP": Currency(code="GBP", symbol="£", label="British Pound"),
    "JPY": Currency(code="JPY", symbol="¥", label="Japanese Yen"),
    "AUD": Currency(code="AUD", symbol="A$", label="Australian Dollar"),
    "CAD": Currency(code="CAD", symbol="C$", label="Canadian Dollar"),
    "SGD": Currency(code="SGD", symbol="S$", label="Singapore Dollar"),
    "CHF": Currency(code="CHF", symbol="CHF", label="Swiss Franc"),
}

DEFAULT_CURRENCY = "HKD"

DEFAULT_EXCHANGE_RATES: Dict[str, float] = {
    "HKD": 1.0,
    "USD": 0.128,
    "RMB": 0.92,
    "EUR": 0.118,
    "GBP": 0.101,
    "JPY": 19.2,
    "AUD": 0.196,
    "CAD": 0.175,
    "SGD": 0.170,
    "CHF": 0.112,
}


def convert_to_currency(amount: float, from_currency: str, to_currency: str, rates: Dict[str, float]) -> float:
    if from_currency == to_currency:
        return amount
    from_rate = rates.get(from_currency)
    to_rate = rates.get(to_currency)
    if from_rate is None or to_rate is None:
        raise ValueError(f"Missing exchange rate for {from_currency} or {to_currency}")
    return amount * (to_rate / from_rate)


def list_currencies() -> list:
    return [{"code": c.code, "symbol": c.symbol, "label": c.label} for c in CURRENCIES.values()]


def get_currency(code: str) -> Currency:
    if code not in CURRENCIES:
        raise ValueError(f"Unknown currency: '{code}'. Available: {list(CURRENCIES.keys())}")
    return CURRENCIES[code]