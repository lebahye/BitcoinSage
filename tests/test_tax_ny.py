"""Tax engine (2026 federal + NY State + NYC): hand-checked worked examples."""
import pytest

from utils import tax_ny as tx

S = tx.TaxProfile(status="single", other_income=100_000, nyc_resident=True)


def test_baseline_100k_single_hand_checked():
    # federal: taxable 83,900 → 1,240 + 4,560 + 7,370 = 13,170
    # NY: taxable 92,000 → 331.50 + 140.80 + 113.30 + 3,604.50 + 669.65 = 4,859.75
    # NYC: 369.36 + 489.06 + 954.75 + 1,627.92 = 3,441.09
    t = tx.total_tax(S)
    assert t["federal"] == pytest.approx(13_170.00)
    assert t["ny"] == pytest.approx(4_859.75)
    assert t["nyc"] == pytest.approx(3_441.09)
    assert t["niit"] == 0


def test_short_vs_long_term_marginal():
    st = tx.year_tax(S, 10_000, 0, tx.Carry())["tax"]
    lt = tx.year_tax(S, 0, 10_000, tx.Carry())["tax"]
    assert st == pytest.approx(10_000 * (0.22 + 0.059 + 0.03876))     # 31.776% combined
    assert lt == pytest.approx(10_000 * (0.15 + 0.059 + 0.03876))     # 24.776%: NY/NYC tax gains as ordinary
    assert tx.year_tax(tx.TaxProfile(other_income=100_000, nyc_resident=False), 10_000, 0, tx.Carry())["tax"] == \
        pytest.approx(10_000 * (0.22 + 0.059))


def test_zero_percent_ltcg_band():
    p = tx.TaxProfile(other_income=30_000, nyc_resident=False)
    r = tx.year_tax(p, 0, 10_000, tx.Carry())
    assert r["detail"]["federal"] == pytest.approx(tx.total_tax(p)["federal"])   # whole gain in the 0% band
    assert r["tax"] == pytest.approx(10_000 * 0.054)                            # NY only (5.4% bracket)


def test_niit_applies_above_threshold():
    p = tx.TaxProfile(other_income=250_000, nyc_resident=False)
    r = tx.year_tax(p, 10_000, 0, tx.Carry())
    assert r["detail"]["niit"] == pytest.approx(380.0)


def test_3000_loss_limit_and_carryforward():
    r = tx.year_tax(S, -50_000, 0, tx.Carry())
    assert r["deduction"] == 3_000
    assert r["carry"].st == pytest.approx(47_000) and r["carry"].lt == 0
    assert r["tax"] == pytest.approx(-3_000 * (0.22 + 0.059 + 0.03876))      # $953.28 saved
    # next year: a $10k long-term gain is wiped out by the short-term carryover, then $3k more is deducted
    r2 = tx.year_tax(S, 0, 10_000, r["carry"])
    assert r2["lt_gain"] == 0 and r2["deduction"] == 3_000
    assert r2["carry"].st == pytest.approx(34_000)


def test_netting_mixed_character():
    n = tx.net_capital(5_000, -8_000, tx.Carry())
    assert n["deduction"] == 3_000 and n["carry"].lt == 0 and n["carry"].st == 0
    n = tx.net_capital(5_000, -20_000, tx.Carry())
    assert n["deduction"] == 3_000 and n["carry"].lt == pytest.approx(12_000)   # keeps long-term character
    n = tx.net_capital(-2_000, 7_000, tx.Carry())
    assert n["lt_gain"] == pytest.approx(5_000) and n["st_gain"] == 0


def test_ira_is_tax_free_and_married_brackets():
    assert tx.year_tax(tx.TaxProfile(account="ira"), 50_000, 0, tx.Carry())["tax"] == 0
    mj = tx.TaxProfile(status="married_joint", other_income=100_000)
    assert tx.total_tax(mj)["federal"] == pytest.approx(2_480 + (67_800 - 24_800) * 0.12)


def test_every_table_is_cited():
    for k in ("fed_brackets", "ltcg", "niit", "loss_limit", "wash_sale", "ny_rates", "nyc_rates", "schwab_fifo"):
        assert tx.SOURCES[k][1].startswith("https://")
