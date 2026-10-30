"""run_both.py — запуск Telegram- и MAX-бота на одном хостинге.

Боты используют несовместимые версии pydantic (aiogram 2 -> v1, maxapi -> v2),
поэтому для каждого создаётся собственное venv в каталоге проекта:
.venv_tg и .venv_max. При первом запуске venv создаются и зависимости
устанавливаются автоматически, повторные запуски используют готовые окружения.

Если переменные окружения TG_PYTHON и/или MAX_PYTHON заданы, соответствующий
venv не создаётся — используется указанный интерпретатор.

Супервизор перезапускает упавший процесс через RESTART_DELAY секунд.
Остановка — Ctrl+C (или SIGTERM от панели хостинга).
"""
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

TG_SCRIPT = os.path.join(SCRIPT_DIR, "main.py")
MAX_SCRIPT = os.path.join(SCRIPT_DIR, "max_main.py")

RESTART_DELAY = 5


def _venv_python(venv_dir: str) -> str:
    """Путь к python внутри venv (Windows и Linux)."""
    if os.name == "nt":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


def _requirements_path(name: str) -> str:
    return os.path.join(SCRIPT_DIR, f"requirements-{name}.txt")


def _ensure_environment(name: str) -> str:
    """Создать venv с зависимостями, если его ещё нет. Вернуть путь к python."""
    venv_dir = os.path.join(SCRIPT_DIR, f".venv_{name}")
    python = _venv_python(venv_dir)
    requirements = _requirements_path(name)

    if not os.path.exists(python):
        print(f"[run_both] создаю окружение {name}: {venv_dir}", flush=True)
        subprocess.check_call([sys.executable, "-m", "venv", venv_dir])

    marker = os.path.join(venv_dir, ".requirements_installed")
    need_install = not os.path.exists(marker)
    if not need_install and os.path.exists(requirements):
        need_install = os.path.getmtime(marker) < os.path.getmtime(requirements)

    if need_install:
        print(f"[run_both] устанавливаю зависимости {name}...", flush=True)
        subprocess.check_call(
            [
                python,
                "-m",
                "pip",
                "install",
                "--no-cache-dir",
                "--disable-pip-version-check",
                "-r",
                requirements,
            ]
        )
        with open(marker, "w", encoding="utf-8") as file:
            file.write("ok\n")

    return python


def _resolve_python(name: str, env_var: str) -> str:
    value = os.environ.get(env_var)
    if value:
        print(f"[run_both] {name}: используем {env_var}={value}", flush=True)
        return value
    return _ensure_environment(name)


def spawn(name: str, python: str, script: str):
    print(f"[run_both] запуск {name}: {python} {script}", flush=True)
    return subprocess.Popen([python, script], cwd=SCRIPT_DIR)


def main():
    if not os.path.exists(TG_SCRIPT):
        print(f"[run_both] не найден {TG_SCRIPT}")
        sys.exit(1)
    if not os.path.exists(MAX_SCRIPT):
        print(f"[run_both] не найден {MAX_SCRIPT}")
        sys.exit(1)

    tg_python = _resolve_python("telegram", "TG_PYTHON")
    max_python = _resolve_python("max", "MAX_PYTHON")

    procs = {
        "telegram": spawn("telegram", tg_python, TG_SCRIPT),
        "max": spawn("max", max_python, MAX_SCRIPT),
    }

    try:
        while True:
            time.sleep(RESTART_DELAY)
            for name, (python, script) in {
                "telegram": (tg_python, TG_SCRIPT),
                "max": (max_python, MAX_SCRIPT),
            }.items():
                proc = procs[name]
                code = proc.poll()
                if code is not None:
                    print(
                        f"[run_both] {name} завершился с кодом {code}, "
                        f"перезапуск через {RESTART_DELAY} c...",
                        flush=True,
                    )
                    time.sleep(RESTART_DELAY)
                    procs[name] = spawn(name, python, script)
    except KeyboardInterrupt:
        print("\n[run_both] остановка ботов...", flush=True)
    finally:
        for proc in procs.values():
            if proc.poll() is None:
                proc.terminate()
        for proc in procs.values():
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
