from utils.tickers import resolve, resolve_all, resolve_keys, MINING_STOCKS, WATCHLIST


def test_bitf_maps_to_keel():
    assert resolve("BITF") == "KEEL"
    assert resolve("bitf") == "KEEL"
    assert resolve("RIOT") == "RIOT"


def test_resolve_all_dedupes():
    assert resolve_all(["BITF", "KEEL", "RIOT"]) == ["KEEL", "RIOT"]


def test_resolve_keys_prefers_current_symbol():
    assert resolve_keys({"BITF": 1, "KEEL": 2}) == {"KEEL": 2}
    assert resolve_keys({"BITF": 1}) == {"KEEL": 1}


def test_lists_have_no_old_symbols():
    assert "BITF" not in MINING_STOCKS and "BITF" not in WATCHLIST
    assert set(WATCHLIST) <= set(MINING_STOCKS)
