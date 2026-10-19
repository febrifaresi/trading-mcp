from trading_mcp.execution.config import ExecutionConfig
from trading_mcp.execution.risk_manager import RiskManager


def _make_config(tmp_path, **overrides) -> ExecutionConfig:
    defaults = dict(
        state_path=str(tmp_path / "state.json"),
        kill_switch_path=str(tmp_path / "KILL_SWITCH"),
        max_daily_loss_usd=10.0,
        max_open_positions=1,
        max_position_usd=50.0,
        risk_per_trade_pct=1.0,
    )
    defaults.update(overrides)
    return ExecutionConfig(**defaults)


def test_kill_switch_blocks_new_entry(tmp_path):
    config = _make_config(tmp_path)
    rm = RiskManager(config)

    (tmp_path / "KILL_SWITCH").write_text("stop")

    ok, reason = rm.can_open_new_position("BTC/USDT")
    assert ok is False
    assert "Kill switch" in reason


def test_no_kill_switch_allows_entry(tmp_path):
    config = _make_config(tmp_path)
    rm = RiskManager(config)

    ok, reason = rm.can_open_new_position("BTC/USDT")
    assert ok is True


def test_daily_loss_circuit_breaker_blocks_new_entry(tmp_path):
    config = _make_config(tmp_path, max_daily_loss_usd=10.0)
    rm = RiskManager(config)

    rm.state.add_realized_pnl(-15.0)

    assert rm.daily_loss_breached() is True
    ok, reason = rm.can_open_new_position("BTC/USDT")
    assert ok is False
    assert "Circuit breaker" in reason


def test_daily_loss_within_limit_allows_entry(tmp_path):
    config = _make_config(tmp_path, max_daily_loss_usd=10.0)
    rm = RiskManager(config)

    rm.state.add_realized_pnl(-5.0)

    assert rm.daily_loss_breached() is False
    ok, _ = rm.can_open_new_position("BTC/USDT")
    assert ok is True


def test_max_open_positions_blocks_new_symbol(tmp_path):
    config = _make_config(tmp_path, max_open_positions=1)
    rm = RiskManager(config)

    rm.register_open("BTC/USDT", entry_price=50000, qty=0.001, stop_price=49000, target_price=52000)

    ok, reason = rm.can_open_new_position("ETH/USDT")
    assert ok is False
    assert "max_open_positions" in reason


def test_existing_position_blocks_duplicate_entry(tmp_path):
    config = _make_config(tmp_path, max_open_positions=5)
    rm = RiskManager(config)

    rm.register_open("BTC/USDT", entry_price=50000, qty=0.001, stop_price=49000, target_price=52000)

    ok, reason = rm.can_open_new_position("BTC/USDT")
    assert ok is False
    assert "Sudah ada posisi" in reason


def test_position_sizing_caps_at_max_position_usd(tmp_path):
    config = _make_config(tmp_path, max_position_usd=50.0, risk_per_trade_pct=50.0)
    rm = RiskManager(config)

    # Balance besar + risk_pct besar -> tanpa cap akan jauh > max_position_usd
    qty, stop, target = rm.calculate_position_size(balance_quote=100_000, entry_price=100.0, atr=1.0)

    position_usd = qty * 100.0
    assert position_usd <= 50.0 + 1e-6
    assert stop < 100.0
    assert target > 100.0


def test_position_sizing_capped_by_balance(tmp_path):
    config = _make_config(tmp_path, max_position_usd=1000.0, risk_per_trade_pct=100.0)
    rm = RiskManager(config)

    qty, _, _ = rm.calculate_position_size(balance_quote=20.0, entry_price=100.0, atr=1.0)

    assert qty * 100.0 <= 20.0 + 1e-6


def test_position_sizing_zero_on_invalid_inputs(tmp_path):
    config = _make_config(tmp_path)
    rm = RiskManager(config)

    qty, _, _ = rm.calculate_position_size(balance_quote=1000.0, entry_price=0.0, atr=1.0)
    assert qty == 0.0

    qty, _, _ = rm.calculate_position_size(balance_quote=1000.0, entry_price=100.0, atr=0.0)
    assert qty == 0.0


def test_register_close_computes_pnl_and_updates_daily_tracker(tmp_path):
    config = _make_config(tmp_path)
    rm = RiskManager(config)

    rm.register_open("BTC/USDT", entry_price=100.0, qty=2.0, stop_price=95.0, target_price=110.0)
    pnl = rm.register_close("BTC/USDT", exit_price=110.0)

    assert pnl == 20.0
    assert rm.get_position("BTC/USDT") is None
    assert rm.state.today_realized_pnl() == 20.0
