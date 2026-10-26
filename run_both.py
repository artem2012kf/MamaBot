"""run_both.py — запуск Telegram-бота и MAX-бота на одном хостинге.

ВАЖНО: aiogram 2.x (нужен main.py) требует pydantic v1, а maxapi требует
pydantic v2. Эти библиотеки не могут жить в одном интерпретаторе, поэтому
боты запускаются ДВУМЯ ОТДЕЛЬНЫМИ ПРОЦЕССАМИ, но работают с одними и теми же
базами данных (sbor.db и database.db) и общим файлом лога bot.log.

Если оба бота запускаются одним интерпретатором (например, когда main.py
переведён на aiogram 3), просто запустите: python run_both.py

Если на хостинге два разных окружения (venv), укажите пути к их python:
    TG_PYTHON=/путь/venv_tg/bin/python MAX_PYTHON=/путь/venv_max/bin/python python run_both.py

Супервизор перезапускает упавший бот через 5 секунд. Остановка — Ctrl+C.
"""
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

TG_SCRIPT = os.path.join(SCRIPT_DIR, "main.py")
MAX_SCRIPT = os.path.join(SCRIPT_DIR, "max_main.py")

# Разные интерпретаторы для разных окружений (по умолчанию — текущий python)
TG_PYTHON = os.environ.get("TG_PYTHON", sys.executable)
MAX_PYTHON = os.environ.get("MAX_PYTHON", sys.executable)

RESTART_DELAY = 5  # секунд до перезапуска упавшего бота


def spawn(name: str, python: str, script: str):
    print(f"[run_both] Запуск {name}: {python} {script}")
    return subprocess.Popen(
        [python, script],
        cwd=SCRIPT_DIR,
    )


def main():
    if not os.path.exists(TG_SCRIPT):
        print(f"[run_both] Не найден {TG_SCRIPT}")
        sys.exit(1)
    if not os.path.exists(MAX_SCRIPT):
        print(f"[run_both] Не найден {MAX_SCRIPT}")
        sys.exit(1)

    procs = {}

    def start(name, python, script):
        procs[name] = spawn(name, python, script)

    try:
        start("telegram", TG_PYTHON, TG_SCRIPT)
        start("max", MAX_PYTHON, MAX_SCRIPT)

        while True:
            time.sleep(RESTART_DELAY)
            for name, (python, script) in {
                "telegram": (TG_PYTHON, TG_SCRIPT),
                "max": (MAX_PYTHON, MAX_SCRIPT),
            }.items():
                proc = procs[name]
                code = proc.poll()
                if code is not None:
                    print(f"[run_both] {name} завершился с кодом {code}, перезапуск через {RESTART_DELAY} c...")
                    time.sleep(RESTART_DELAY)
                    start(name, python, script)
    except KeyboardInterrupt:
        print("\n[run_both] Остановка ботов...")
        for proc in procs.values():
            proc.terminate()
        for proc in procs.values():
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
