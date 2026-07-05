"""Document renderers. Every checkable figure is emitted on a line with a CANONICAL
label so the consistency checker and the flaw-injector can find it reliably; the
rest is prose. All figures come from the world state, so a clean corpus ties out.
"""
from __future__ import annotations

# Canonical labels (shared with check.py / inject.py -- do not drift)
LBL_MGMT_FEE = "Management fee:"
LBL_CARRY = "Carried interest:"
LBL_HURDLE = "Preferred return (hurdle):"
LBL_FUND_SIZE = "Total commitments (fund size):"
LBL_LP_COMMIT = "LP commitment:"
LBL_DISTRIB = "Cumulative distributions:"
LBL_ENDING_NAV = "Ending capital account (NAV):"
LBL_CONTRIB = "Contributions to date:"
LBL_ALLOC_GAIN = "Allocated net gain:"
LBL_ALLOC_FEES = "Allocated management fees:"


def fmt_money(x) -> str:
    return "$" + f"{int(round(float(x))):,}"


def fmt_pct(x) -> str:
    return f"{float(x):.1f}%"


def render_ppm(w) -> str:
    return f"""# Private Placement Memorandum -- {w.fund_name}

CONFIDENTIAL. This memorandum describes an offering of limited partnership interests in
{w.fund_name} (the "Fund"), a {w.strategy} fund managed by {w.manager_name} (the "Manager"),
vintage {w.vintage_year}.

## Key Terms

{LBL_FUND_SIZE} {fmt_money(w.committed_capital)}
{LBL_MGMT_FEE} {fmt_pct(w.mgmt_fee_pct)}
{LBL_CARRY} {fmt_pct(w.carry_pct)}
{LBL_HURDLE} {fmt_pct(w.hurdle_pct)}
Term: {w.term_years} years from final closing.

## Strategy

The Fund pursues {w.strategy} investments in North American companies, seeking control or
significant-minority positions and value creation through operational improvement.

## Risk Factors

Interests are illiquid and non-transferable. Past performance is not indicative of future
results. Fees and carried interest will reduce returns to Limited Partners.
"""


def render_lpa(w) -> str:
    return f"""# Limited Partnership Agreement -- {w.fund_name}

This Agreement governs the rights and obligations of the General Partner and the Limited
Partners of {w.fund_name}.

## Economic Terms

{LBL_MGMT_FEE} {fmt_pct(w.mgmt_fee_pct)}
{LBL_CARRY} {fmt_pct(w.carry_pct)}
{LBL_HURDLE} {fmt_pct(w.hurdle_pct)}
{LBL_LP_COMMIT} {fmt_money(w.lp_commitment)}

## Distribution Waterfall

Distributions are made (i) return of contributed capital, (ii) a preferred return of
{fmt_pct(w.hurdle_pct)}, (iii) a general-partner catch-up, and (iv) thereafter
{fmt_pct(100 - w.carry_pct)} to the Limited Partners and {fmt_pct(w.carry_pct)} to the
General Partner as carried interest.
"""


def render_ddq(w) -> str:
    return f"""# Due Diligence Questionnaire (DDQ) -- {w.manager_name}

Q: What management fee does the Fund charge?
{LBL_MGMT_FEE} {fmt_pct(w.mgmt_fee_pct)} per annum on committed capital during the investment period.

Q: What is the carried interest?
{LBL_CARRY} {fmt_pct(w.carry_pct)} subject to the preferred return.

Q: Who is the Manager and what is the strategy?
A: {w.manager_name} manages the Fund pursuing a {w.strategy} strategy.
"""


def render_adv(w) -> str:
    return f"""# Form ADV Part 2A -- {w.manager_name}

## Advisory Business

{w.manager_name} (the "Adviser") provides investment advice to pooled investment vehicles,
including {w.fund_name}. Regulatory assets under management (AUM): {fmt_money(w.manager_aum)}.

## Fees and Compensation

{LBL_FUND_SIZE} {fmt_money(w.committed_capital)}
{LBL_MGMT_FEE} {fmt_pct(w.mgmt_fee_pct)}

## Conflicts of Interest

The Adviser and its affiliates may have conflicts relating to allocation of investment
opportunities and the calculation of fees and carried interest.
"""


def render_k1(w) -> str:
    return f"""# Schedule K-1 (Form 1065) -- 2025 Tax Year

Partnership: {w.fund_name}
Partner: {w.lp_name}

{LBL_LP_COMMIT} {fmt_money(w.lp_commitment)}
{LBL_DISTRIB} {fmt_money(w.distributions)}
{LBL_ENDING_NAV} {fmt_money(w.ending_nav)}

Partner's share of the Partnership's net gain for the year was {fmt_money(w.lp_allocated_gain)},
and allocated management fees were {fmt_money(w.lp_fees)}. This K-1 reconciles to the Partner's
capital account statement.
"""


def render_capital_account(w) -> str:
    return f"""# Limited Partner Capital Account Statement -- {w.lp_name}

Fund: {w.fund_name}. As of {w.as_of}.

{LBL_LP_COMMIT} {fmt_money(w.lp_commitment)}

## Capital Account Rollforward

{LBL_CONTRIB} {fmt_money(w.contributions)}
{LBL_ALLOC_GAIN} {fmt_money(w.lp_allocated_gain)}
{LBL_ALLOC_FEES} {fmt_money(w.lp_fees)}
{LBL_DISTRIB} {fmt_money(w.distributions)}
{LBL_ENDING_NAV} {fmt_money(w.ending_nav)}

Ending capital account = contributions + allocated net gain - allocated management fees -
cumulative distributions.
"""


def render_ic_memo(w) -> str:
    return f"""# Investment Committee Memo -- {w.fund_name}

Recommendation: MAINTAIN the Fund commitment; the portfolio is performing in line with
underwriting.

Portfolio gross value is {fmt_money(w.fund_value)} against {fmt_money(w.fund_cost)} of cost
(gross MOIC {w.fund_value / w.fund_cost:.2f}x). Net to the Limited Partner, the position shows
TVPI {w.tvpi:.2f}x and DPI {w.dpi:.2f}x on {fmt_money(w.contributions)} contributed.

Thesis: the {w.strategy} portfolio ({', '.join(h.name for h in w.holdings)}) has multiple
value-creation levers underway. Key risks are concentration and hold-period extension.
"""


def render_all(w) -> dict:
    return {
        "ppm": render_ppm(w),
        "lpa": render_lpa(w),
        "ddq": render_ddq(w),
        "adv": render_adv(w),
        "k1": render_k1(w),
        "capital_account": render_capital_account(w),
        "ic_memo": render_ic_memo(w),
    }
