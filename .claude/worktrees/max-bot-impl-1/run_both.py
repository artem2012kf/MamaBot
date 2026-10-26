# run_both.py
"""run_both.py – одновременный запуск Telegram‑бота и бота для мессенджера MAX.

Оба бота используют один и тот же набор баз SQLite (`database.db` и `sbor.db`).
Скрипт запускает их в одном asyncio‑event‑loop, поэтому они работают параллельно
и имеют доступ к общим данным без конфликта.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем каталог проекта в `sys.path`, чтобы модули импортировались без проблем
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

# Импортируем функции запуска из существующих файлов
from main import executor as tg_executor, dp as tg_dp, on_startup as tg_startup
from max_main import executor as max_executor, dp as max_dp, on_startup as max_startup

# Настраиваем общий логгер (записываем в один файл `bot.log`)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bot.log", encoding="utf-8")],
)

async def start_telegram():
    """Запускает Telegram‑бота (aiogram)."""
    await tg_startup(tg_dp)
    await tg_executor.start_polling(tg_dp, skip_updates=True)

async def start_max():
    """Запускает бота‑клиента для мессенджера MAX."""
    await max_startup(max_dp)
    await max_executor.start_polling(max_dp, skip_updates=True)

async def main():
    # Запускаем оба бота параллельно в одном event‑loop
    await asyncio.gather(start_telegram(), start_max())

if __name__ == "__main__":
    asyncio.run(main())
