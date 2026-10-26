"""config.example.py — шаблон конфигурации для обоих ботов.

Скопируйте этот файл в config.py и заполните своими значениями:
    cp config.example.py config.py

config.py намеренно исключён из Git (.gitignore) — токены не должны
попадать в репозиторий. Оба бота (Telegram и MAX) читают ОДИН файл
config.py, поэтому на хостинге достаточно одного config.py для обоих.
"""

# ---------- Telegram-бот (main.py) ----------
API = "ТЕЛЕГРАМ_ТОКЕН_БОТА"          # токен от @BotFather
GROUP_ID = 0                          # chat_id группового чата Telegram,
                                      # куда бот отправляет список участников
admins = [0, 0]                       # Telegram user_id администраторов
pol = [0, 0]                          # Telegram user_id пользователей с доступом
MAX_WOMEN = 4                         # лимит девушек (зарезервировано на будущее)

# ---------- MAX-бот (max_main.py) ----------
API_MAX = "МАКС_ТОКЕН_БОТА"           # токен бота из MAX
GROUP_ID_MAX = 0                      # chat_id группового чата MAX
                                      # (узнать: добавьте бота в чат и запустите get_max_chats.py)
admins_max = [0, 0]                   # MAX user_id администраторов
pol_max = [0, 0]                      # MAX user_id пользователей с доступом
