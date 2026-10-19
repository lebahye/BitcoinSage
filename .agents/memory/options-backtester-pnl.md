---
name: Options Backtester P&L Math
description: Correct formula for options strategy edge vs buy-and-hold in options_backtester.py
---

## The Rule
`net_income` passed to `_package_results` must equal `sum(cycle_nets)` — NOT `sum(gross_premiums)`.

`strategy_pnl = bah_pnl + net_income` only gives the correct result when `net_income = sum(cycle_nets)`.

## Why
For covered calls in a bull market, each assigned cycle has:
- `cycle_net = premium - missed_upside` (can be deeply negative)

If you pass only `sum(premiums)`, you double-count the upside:
- `bah_pnl` already includes the full stock run-up
- Adding gross premiums then claims you also collected calls as pure income
- But in assigned cycles you gave away (S_exp - K) × shares of that run-up

## How to Apply
- Track `gross_premiums` (sum of all premiums) separately — show as "Gross Premiums Collected" in UI and use for annual yield % calculation
- Track `net_cycle_total = sum(cycle_nets)` — pass as `net_income`; use as "strategy edge" and in `strategy_pnl`
- `strategy_pnl = bah_pnl + net_income` then correctly equals "what you'd actually have"

## Also Applies To
- Protective puts: `cycle_net = put_payoff - put_cost`; pass `sum(cycle_nets)` as net_income, `-cumulative_cost` as gross_income
- Collar: same pattern — pass `sum(cycle_nets)` as net_income, `cumulative_net_premiums` as gross_income
