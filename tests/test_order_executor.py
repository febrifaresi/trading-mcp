import json

from trading_mcp.execution.config import ExecutionConfig
from trading_mcp.execution.order_executor import OrderExecutor
from trading_mcp.execution.risk_manager import RiskManager
from trading_mcp.execution.signal_generator import Signal
from trading_mcp.execution.trade_logger import TradeLogger


class FakeSignalGenerator:
    """Stub — tidak pernah menyentuh network, cukup return sinyal yang sudah ditentukan test."""

    def __init__(self, signal: Signal):
        self._signal = signal
        self.calls = 0

    def generate(self, symbol: str) -> Signal:
        self.calls += 1
        return self._signal


class FakeExchangeClient:
    """Tracks pemanggilan — test memastikan ini TIDAK pernah dipanggil saat dry_run."""

    def __init__(self, balance: float = 1000.0):
        self.balance = balance
        self.buy_calls: list[tuple[str, float]] = []
        self.sell_calls: list[tuple[str, float]] = []

    def fetch_balance_quote(self, quote: str = "USDT") -> float:
        return self.balance

    def create_market_buy(self, symbol: str, amount: float) -> dict:
        self.buy_calls.append((symbol, amount))
        return {"id": "fake-buy-1", "symbol": symbol, "amount": amount}

    def create_market_sell(self, symbol: str, amount: float) -> dict:
        self.sell_calls.append((symbol, amount))
        return {"id": "fake-sell-1", "symbol": symbol, "amount": amount}


def _make_config(tmp_path, **overrides) -> ExecutionConfig:
    defaults = dict(
        state_path=str(tmp_path / "state.json"),
        kill_switch_path=str(tmp_path / "KILL_SWITCH"),
        log_path=str(tmp_path / "trade_log.jsonl"),
        max_open_positions=5,
        max_position_usd=50.0,
        risk_per_trade_pct=1.0,
        trading_mode="dry_run",
    )
    defaults.update(overrides)
    return ExecutionConfig(**defaults)


def _read_log_events(config: ExecutionConfig) -> list[dict]:
    with open(config.log_path) as f:
        return [json.loads(line) for line in f if line.strip()]


def test_dry_run_never_calls_exchange_on_entry(tmp_path):
    config = _make_config(tmp_path, trading_mode="dry_run")
    signal = Signal(symbol="BTC/USDT", direction="LONG_ENTRY", score=7, reasons=["ok"], price=100.0, atr=2.0)

    exchange = FakeExchangeClient()
    rm = RiskManager(config)
    executor = OrderExecutor(
        config=config,
        risk_manager=rm,
        signal_generator=FakeSignalGenerator(signal),
        logger=TradeLogger(config.log_path),
        exchange_client=exchange,
    )

    executor.process_symbol("BTC/USDT")

    assert exchange.buy_calls == []  # dry_run tidak pernah kirim order sungguhan
    assert rm.get_position("BTC/USDT") is not None

    events = _read_log_events(config)
    assert any(e["event"] == "order" and e["mode"] == "dry_run" for e in events)


def test_live_mode_calls_exchange_after_risk_pass(tmp_path):
    config = _make_config(
        tmp_path,
        trading_mode="live",
        use_testnet=False,
        api_key="key",
        api_secret="secret",
    )
    signal = Signal(symbol="BTC/USDT", direction="LONG_ENTRY", score=7, reasons=["ok"], price=100.0, atr=2.0)

    exchange = FakeExchangeClient(balance=1000.0)
    rm = RiskManager(config)
    executor = OrderExecutor(
        config=config,
        risk_manager=rm,
        signal_generator=FakeSignalGenerator(signal),
        logger=TradeLogger(config.log_path),
        exchange_client=exchange,
    )

    executor.process_symbol("BTC/USDT")

    assert len(exchange.buy_calls) == 1
    assert exchange.buy_calls[0][0] == "BTC/USDT"
    assert rm.get_position("BTC/USDT") is not None


def test_kill_switch_rejects_entry_and_skips_exchange(tmp_path):
    config = _make_config(tmp_path, trading_mode="dry_run")
    (tmp_path / "KILL_SWITCH").write_text("stop")

    signal = Signal(symbol="BTC/USDT", direction="LONG_ENTRY", score=7, reasons=["ok"], price=100.0, atr=2.0)
    exchange = FakeExchangeClient()
    rm = RiskManager(config)
    executor = OrderExecutor(
        config=config,
        risk_manager=rm,
        signal_generator=FakeSignalGenerator(signal),
        logger=TradeLogger(config.log_path),
        exchange_client=exchange,
    )

    executor.process_symbol("BTC/USDT")

    assert exchange.buy_calls == []
    assert rm.get_position("BTC/USDT") is None

    events = _read_log_events(config)
    assert any(e["event"] == "risk_rejected" for e in events)


def test_exit_on_stop_loss_closes_position(tmp_path):
    config = _make_config(tmp_path, trading_mode="dry_run")
    rm = RiskManager(config)
    rm.register_open("BTC/USDT", entry_price=100.0, qty=1.0, stop_price=95.0, target_price=110.0)

    # Harga sekarang jatuh ke bawah stop -> harus exit
    signal = Signal(symbol="BTC/USDT", direction="NONE", score=2, reasons=[], price=94.0, atr=2.0)
    exchange = FakeExchangeClient()
    executor = OrderExecutor(
        config=config,
        risk_manager=rm,
        signal_generator=FakeSignalGenerator(signal),
        logger=TradeLogger(config.log_path),
        exchange_client=exchange,
    )

    executor.process_symbol("BTC/USDT")

    assert rm.get_position("BTC/USDT") is None
    assert rm.state.today_realized_pnl() == -6.0  # (94 - 100) * 1.0

    events = _read_log_events(config)
    assert any(e["event"] == "close" and e["reason"] == "stop_loss" for e in events)


def test_exit_on_signal_flip_closes_position(tmp_path):
    config = _make_config(tmp_path, trading_mode="dry_run")
    rm = RiskManager(config)
    rm.register_open("BTC/USDT", entry_price=100.0, qty=1.0, stop_price=90.0, target_price=120.0)

    # Harga masih dalam range stop/target, tapi sinyal berbalik BEARISH kuat
    signal = Signal(symbol="BTC/USDT", direction="EXIT", score=7, reasons=["bearish"], price=105.0, atr=2.0)
    executor = OrderExecutor(
        config=config,
        risk_manager=rm,
        signal_generator=FakeSignalGenerator(signal),
        logger=TradeLogger(config.log_path),
        exchange_client=FakeExchangeClient(),
    )

    executor.process_symbol("BTC/USDT")

    assert rm.get_position("BTC/USDT") is None
    events = _read_log_events(config)
    assert any(e["event"] == "close" and e["reason"] == "signal_exit" for e in events)


def test_holds_position_when_no_exit_condition(tmp_path):
    config = _make_config(tmp_path, trading_mode="dry_run")
    rm = RiskManager(config)
    rm.register_open("BTC/USDT", entry_price=100.0, qty=1.0, stop_price=90.0, target_price=120.0)

    signal = Signal(symbol="BTC/USDT", direction="NONE", score=3, reasons=[], price=105.0, atr=2.0)
    executor = OrderExecutor(
        config=config,
        risk_manager=rm,
        signal_generator=FakeSignalGenerator(signal),
        logger=TradeLogger(config.log_path),
        exchange_client=FakeExchangeClient(),
    )

    executor.process_symbol("BTC/USDT")

    assert rm.get_position("BTC/USDT") is not None
