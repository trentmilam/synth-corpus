"""The world state: one seeded, internally-consistent source of truth.

Every document renders from this; every cross-document figure derives from it, so
the clean corpus ties out by construction. Derived figures (ownership, allocated
gain, capital-account NAV, TVPI/DPI) are computed exactly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

_FUND_NAMES = [
    "Meridian Capital Partners III, L.P.",
    "Ironwood Private Equity IV, L.P.",
    "Blackspire Growth Fund II, L.P.",
    "Cedarpoint Buyout Partners V, L.P.",
]
_MANAGERS = {
    "Meridian Capital Partners III, L.P.": "Meridian Capital Management, LLC",
    "Ironwood Private Equity IV, L.P.": "Ironwood Advisors, LLC",
    "Blackspire Growth Fund II, L.P.": "Blackspire Asset Management, LLC",
    "Cedarpoint Buyout Partners V, L.P.": "Cedarpoint Partners, LLC",
}
_LPS = ["The Harrington Family Trust", "Whitmore Foundation", "Ellison 2019 Irrevocable Trust", "Castellan Family Office LLC"]
_STRATS = ["middle-market buyout", "growth equity", "lower-middle-market control buyout"]
_HOLDINGS = ["Alpha Industries", "Beta Systems", "Gamma Health", "Delta Logistics", "Epsilon Software", "Zenith Materials"]


@dataclass
class Holding:
    name: str
    cost: float
    value: float


@dataclass
class World:
    seed: int
    fund_name: str
    manager_name: str
    strategy: str
    vintage_year: int
    committed_capital: float
    mgmt_fee_pct: float
    carry_pct: float
    hurdle_pct: float
    term_years: int
    manager_aum: float
    lp_name: str
    lp_commitment: float
    contributions: float
    distributions: float
    total_mgmt_fees: float
    as_of: str
    holdings: list = field(default_factory=list)

    # --- derived (computed exactly) ---
    @property
    def ownership_frac(self) -> float:
        return self.lp_commitment / self.committed_capital

    @property
    def fund_cost(self) -> float:
        return sum(h.cost for h in self.holdings)

    @property
    def fund_value(self) -> float:
        return sum(h.value for h in self.holdings)

    @property
    def fund_gain(self) -> float:
        return self.fund_value - self.fund_cost

    @property
    def lp_allocated_gain(self) -> float:
        return round(self.ownership_frac * self.fund_gain, 0)

    @property
    def lp_fees(self) -> float:
        return round(self.ownership_frac * self.total_mgmt_fees, 0)

    @property
    def ending_nav(self) -> float:
        return self.contributions + self.lp_allocated_gain - self.lp_fees - self.distributions

    @property
    def tvpi(self) -> float:
        return (self.ending_nav + self.distributions) / self.contributions

    @property
    def dpi(self) -> float:
        return self.distributions / self.contributions

    def summary(self) -> dict:
        return {
            "seed": self.seed, "fund_name": self.fund_name, "manager_name": self.manager_name,
            "strategy": self.strategy, "vintage_year": self.vintage_year,
            "committed_capital": self.committed_capital, "mgmt_fee_pct": self.mgmt_fee_pct,
            "carry_pct": self.carry_pct, "hurdle_pct": self.hurdle_pct, "term_years": self.term_years,
            "manager_aum": self.manager_aum, "lp_name": self.lp_name, "lp_commitment": self.lp_commitment,
            "contributions": self.contributions, "distributions": self.distributions,
            "total_mgmt_fees": self.total_mgmt_fees, "as_of": self.as_of,
            "ownership_frac": self.ownership_frac, "fund_cost": self.fund_cost,
            "fund_value": self.fund_value, "lp_allocated_gain": self.lp_allocated_gain,
            "lp_fees": self.lp_fees, "ending_nav": self.ending_nav,
            "tvpi": round(self.tvpi, 4), "dpi": round(self.dpi, 4),
            "holdings": [{"name": h.name, "cost": h.cost, "value": h.value} for h in self.holdings],
        }


def build_world(seed: int = 20260704) -> World:
    rng = np.random.default_rng(seed)

    def pick(seq):
        return seq[int(rng.integers(len(seq)))]

    fund_name = pick(_FUND_NAMES)
    committed_capital = float(pick([300, 500, 750, 1000])) * 1e6
    mgmt_fee_pct = float(pick([1.5, 2.0]))
    vintage_year = int(pick([2019, 2020, 2021, 2022]))
    lp_commitment = float(pick([5, 10, 15, 25])) * 1e6
    called_pct = float(pick([0.6, 0.7, 0.75, 0.8]))
    contributions = round(lp_commitment * called_pct, -3)
    distributions = round(contributions * float(pick([0.2, 0.3, 0.4])), -3)
    total_mgmt_fees = round(mgmt_fee_pct / 100.0 * committed_capital * 3.0, -3)
    manager_aum = committed_capital * float(pick([2.0, 2.4, 3.0]))

    names = list(_HOLDINGS)
    idx = rng.choice(len(names), size=4, replace=False)
    holdings = []
    for i in idx:
        cost = round(float(pick([60, 80, 90, 120])) * 1e6, -3)
        value = round(cost * float(pick([0.7, 1.2, 1.5, 1.8])), -3)
        holdings.append(Holding(names[int(i)], cost, value))

    return World(
        seed=seed, fund_name=fund_name, manager_name=_MANAGERS[fund_name],
        strategy=pick(_STRATS), vintage_year=vintage_year, committed_capital=committed_capital,
        mgmt_fee_pct=mgmt_fee_pct, carry_pct=20.0, hurdle_pct=8.0, term_years=10,
        manager_aum=manager_aum, lp_name=pick(_LPS), lp_commitment=lp_commitment,
        contributions=contributions, distributions=distributions, total_mgmt_fees=total_mgmt_fees,
        as_of="December 31, 2025", holdings=holdings,
    )
