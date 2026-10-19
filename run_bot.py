"""
Entrypoint untuk automation bot (eksekusi order otomatis).

Cara run:
    python run_bot.py

Default: dry_run + testnet — TIDAK mengirim order sungguhan sampai kamu
sengaja set TRADING_MODE=live dan BYBIT_TESTNET=false di .env.
Lihat README bagian "Automation" sebelum menyalakan mode live.
"""

from dotenv import load_dotenv

load_dotenv()

from trading_mcp.execution.config import ExecutionConfig
from trading_mcp.execution.bot import AutomationBot


def main() -> None:
    config = ExecutionConfig.from_env()
    bot = AutomationBot(config)
    bot.run_forever()


if __name__ == "__main__":
    main()
