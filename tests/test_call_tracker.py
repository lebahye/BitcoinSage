import os
from utils import call_tracker as ct
from utils import notifier
from utils.holding_advisor import Advice, Check


def _adv(action, status="good", score=0):
    return Advice("RIOT", action, "High", f"{action} it", score, 10,
                  checks=[Check("Trend", status, "x")], facts={"price": 10.0})


def test_first_check_silent_then_change_detected(tmp_path):
    p = str(tmp_path / "calls.json")
    assert ct.record("RIOT", ct.snapshot(_adv("HOLD")), p) is None
    assert ct.record("RIOT", ct.snapshot(_adv("HOLD")), p) is None
    ch = ct.record("RIOT", ct.snapshot(_adv("TRIM", "bad", 4)), p)
    assert ch and ch["old"]["action"] == "HOLD" and ch["new"]["action"] == "TRIM"
    assert any("Trend: good → bad" in w for w in ch["why"])
    # banner persists across reruns until acknowledged
    assert ct.record("RIOT", ct.snapshot(_adv("TRIM", "bad", 4)), p) is None
    assert ct.pending("RIOT", p) is not None
    ct.acknowledge("RIOT", p)
    assert ct.pending("RIOT", p) is None and len(ct.history("RIOT", p)) == 1
    assert "HOLD → TRIM" in ct.format_change(ch)


def test_notifier_off_by_default_and_blocked_in_tests(tmp_path):
    s = notifier.load_settings(str(tmp_path / "none.json"))
    assert s["enabled"] is False
    env = {"TELEGRAM_BOT_TOKEN": "x", "TELEGRAM_CHAT_ID": "y"}
    assert notifier.channels_to_use(s, env) == []                       # off by default
    assert notifier.channels_to_use({**s, "enabled": True}, env) == ["telegram"]
    assert notifier.channels_to_use({**s, "enabled": True}, {**env, "PYTEST_CURRENT_TEST": "1"}) == []
    assert notifier.channels_to_use({**s, "enabled": True}, {}) == []   # no secrets → nothing
    # real environment under pytest: notify() must send nothing
    assert os.environ.get("PYTEST_CURRENT_TEST")
    assert notifier.notify("t", "t", {**s, "enabled": True}) == {}
