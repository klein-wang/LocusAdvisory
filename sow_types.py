from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class SOWType:
    key: str
    label: str
    is_asset: bool
    default_annual_growth: float
    default_monthly_contribution: float = 0.0

SOW_TYPES: Dict[str, SOWType] = {
    "cash": SOWType(
        key="cash",
        label="Cash & Equivalents",
        is_asset=True,
        default_annual_growth=0.03,
    ),
    "income": SOWType(
        key="income",
        label="Stable Income",
        is_asset=True,
        default_annual_growth=0.04,
        default_monthly_contribution=0.0,
    ),
    "investment": SOWType(
        key="investment",
        label="Investments",
        is_asset=True,
        default_annual_growth=0.07,
    ),
    "retirement": SOWType(
        key="retirement",
        label="Retirement Accounts",
        is_asset=True,
        default_annual_growth=0.07,
    ),
    "real_estate": SOWType(
        key="real_estate",
        label="Real Estate",
        is_asset=True,
        default_annual_growth=0.04,
    ),
    "crypto": SOWType(
        key="crypto",
        label="Crypto Assets",
        is_asset=True,
        default_annual_growth=0.10,
    ),
    "personal_property": SOWType(
        key="personal_property",
        label="Personal Property",
        is_asset=True,
        default_annual_growth=0.02,
    ),
    "credit": SOWType(
        key="credit",
        label="Credit & Debt",
        is_asset=False,
        default_annual_growth=0.05,
    ),
}

DEFAULT_SOW_TYPE = "investment"


def get_sow_type(key: str) -> SOWType:
    if key not in SOW_TYPES:
        raise ValueError(
            f"Unknown SOW type: '{key}'. "
            f"Available types: {', '.join(SOW_TYPES.keys())}"
        )
    return SOW_TYPES[key]


def list_sow_types() -> list:
    return list(SOW_TYPES.keys())