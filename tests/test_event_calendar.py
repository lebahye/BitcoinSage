from datetime import date
from utils import event_calendar as ec


def test_halving_math():
    h = ec.halving_estimate(972_201)
    assert h["halving_height"] == 1_050_000 and h["blocks_left"] == 77_799 and h["reward_after"] == 1.5625
    assert ec.halving_estimate(840_000)["halving_height"] == 1_050_000


def test_schedules_are_sane():
    ends = [ec._d(e) for _, e, _ in ec.FOMC_MEETINGS]
    assert ends == sorted(ends) and len(ends) == 16
    assert all(ec._d(s) < ec._d(e) for s, e, _ in ec.FOMC_MEETINGS)
    cpi = [ec._d(d) for _, d in ec.CPI_RELEASES]
    assert cpi == sorted(cpi)


def test_calendar_flags_14_days():
    today = date(2026, 10, 19)
    ev = ec.build_calendar(today, {"RIOT": [date(2026, 10, 29)], "OLD": [date(2026, 7, 1)]}, 972_201)
    flags = ec.flagged(ev, today)
    kinds = {(e.kind, e.when) for e in flags}
    assert ("Earnings", date(2026, 10, 29)) in kinds and ("FOMC", date(2026, 10, 28)) in kinds
    assert all(e.kind != "CPI" for e in flags)          # Nov 10 is 22 days away
    assert not any("OLD" in e.title for e in ev)         # past dates dropped
    assert any(e.kind == "Halving" for e in ev) and not any(e.kind == "Halving" for e in flags)
