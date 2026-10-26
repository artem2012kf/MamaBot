"""run_max.py — запуск ТОЛЬКО MAX-бота (Telegram-бот сейчас выключен).

Использование на хостинге:
    python run_max.py                 # обычная проверка токена/конфига
    MAX_TOKEN=... GROUP_ID=... ADMIN_IDS=1,2 python run_max.py   # без config.py

Скрипт запускает max_main.py отдельным процессом и перезапускает его через
5 секунд, если бот упал (супервизор). Остановка — Ctrl+C или SIGTERM.

Когда понадобится вернуть Telegram-бот к работе вместе с MAX — используйте
run_both.py (он запускает оба процесса; базы SQLite уже настроены на
параллельный доступ: WAL + busy_timeout в shared/db.py).
"""
import os
import signal
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_SCRIPT = os.path.join(SCRIPT_DIR, "max_main.py")
RESTART_DELAY = 5  # секунд до перезапуска упавшего бота


def spawn():
    print(f"[run_max] Запуск MAX-бота: {sys.executable} {MAX_SCRIPT}")
    return subprocess.Popen([sys.executable, MAX_SCRIPT], cwd=SCRIPT_DIR)


def main():
    if not os.path.exists(MAX_SCRIPT):
        print(f"[run_max] Не найден {MAX_SCRIPT}")
        sys.exit(1)

    stop = {"flag": False}

    def on_signal(signum, frame):
        stop["flag"] = True

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    proc = spawn()
    try:
        while not stop["flag"]:
            code = proc.poll()
            if code is None:
                time.sleep(1)
                continue
            if stop["flag"]:
                break
            print(f"[run_max] MAX-бот завершился с кодом {code}, "
                  f"перезапуск через {RESTART_DELAY} c...")
            for _ in range(RESTART_DELAY):
                if stop["flag"]:
                    break
                time.sleep(1)
            if stop["flag"]:
                break
            proc = spawn()
    finally:
        print("[run_max] Остановка MAX-бота...")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
