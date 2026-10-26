"""active.py — работа с таблицей Users базы database.db.

Схема таблицы (версия 2):
    id_tg   INTEGER PRIMARY KEY -- Telegram id (NULL для пользователей MAX)
    id_max  INTEGER UNIQUE      -- MAX id (NULL для пользователей Telegram)
    username TEXT               -- @username из Telegram (в MAX юзернеймов нет)
    first_name TEXT             -- имя пользователя
    gender TEXT                 -- 'М' / 'Ж' / NULL
    block INTEGER               -- 0 — активен, 1 — заблокирован

Боты работают двумя процессами с одной базой, поэтому все соединения
настраиваются через configure_connection() (WAL + busy_timeout), а каждое
чтение/запись выполняется НОВЫМ коротким соединением, чтобы второй процесс
всегда видел свежие данные.

Важно: идентификаторы Telegram и MAX — разные числа даже у одного человека.
Функции принимают пару (id_tg, id_max); там, где известен только один канал,
второй аргумент равен None и поиск идёт по нему одному.
"""
import sqlite3

from shared.db import configure_connection, DB_TIMEOUT

DATABASE_NAME = "database.db"


def create_connection():
    """Создает соединение с базой данных SQLite (WAL, для совместной работы двух ботов)."""
    conn = None
    try:
        conn = configure_connection(sqlite3.connect(DATABASE_NAME, timeout=DB_TIMEOUT))
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to the database: {e}")
    return conn


# Соединение модуля нужно только для миграции схемы при импорте.
connection = create_connection()
cursor = connection.cursor() if connection is not None else None

# ---------- Миграция старой схемы (id -> id_tg + id_max) ----------
if cursor is not None:
    try:
        # Таблица в актуальной схеме.
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS Users_new(
                id_tg INTEGER PRIMARY KEY,
                id_max INTEGER UNIQUE,
                username TEXT,
                first_name TEXT,
                gender TEXT,
                block INTEGER DEFAULT 0
            );"""
        )
        columns = {row[1] for row in cursor.execute("PRAGMA table_info(Users)").fetchall()}
        if "id" in columns:
            # Старая схема: столбец id — это Telegram id. Переносим его в id_tg
            # и добавляем id_max через пересоздание таблицы (работает на любой
            # версии SQLite, в отличие от ALTER TABLE ... DROP COLUMN).
            cursor.execute(
                """INSERT OR IGNORE INTO Users_new(id_tg, id_max, username, first_name, gender, block)
                   SELECT id, NULL, username, first_name, gender, COALESCE(block, 0) FROM Users;"""
            )
            cursor.execute("DROP TABLE Users")
            cursor.execute("ALTER TABLE Users_new RENAME TO Users")
            connection.commit()
            print("Миграция схемы Users завершена: id -> id_tg, добавлен id_max.")
        else:
            # Таблицы Users ещё нет (первый запуск) или она уже в новой схеме.
            if not columns:
                cursor.execute("ALTER TABLE Users_new RENAME TO Users")
                connection.commit()
            else:
                cursor.execute("DROP TABLE Users_new")
    except sqlite3.Error as e:
        print(f"Не удалось выполнить миграцию схемы Users: {e}")
    finally:
        connection.close()


def _find(conn, id_tg=None, id_max=None):
    """Возвращает строку пользователя по любому из известных id."""
    if id_tg is not None:
        row = conn.execute("SELECT * FROM Users WHERE id_tg = ?", (id_tg,)).fetchone()
        if row:
            return row
    if id_max is not None:
        row = conn.execute("SELECT * FROM Users WHERE id_max = ?", (id_max,)).fetchone()
        if row:
            return row
    return None


def add_user(id_tg=None, username=None, first_name=None, gender=None, id_max=None):
    """Добавляет пользователя или привязывает второй мессенджер к существующему.

    Логика:
      1. Если запись уже есть по id_tg ИЛИ id_max — дописываем отсутствующий
         id второго канала и обновляем имя/юзернейм/пол. Так человек,
         зарегистрированный через Telegram, сможет работать и через MAX:
         MAX-бот найдёт его по first_name и привяжет id_max к той же записи.
      2. Если записи нет — создаём новую (block = 0).
    """
    if id_tg is None and id_max is None:
        print("add_user: оба id равны None — пропускаем")
        return
    conn = create_connection()
    if conn is None:
        return
    try:
        row = _find(conn, id_tg, id_max)
        if row is None:
            conn.execute(
                "INSERT INTO Users (id_tg, id_max, username, first_name, gender, block)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (id_tg, id_max, username, first_name, gender, 0),
            )
            conn.commit()
            print(f"User added to the database: id_tg={id_tg}, id_max={id_max}.")
            return

        cur_id_tg, cur_id_max = row[0], row[1]
        # Привязка второго канала: нашли по id_max, пришёл Telegram id (и наоборот).
        if id_tg is not None and cur_id_tg is None:
            conn.execute("UPDATE Users SET id_tg = ? WHERE id_max = ?", (id_tg, id_max))
            cur_id_tg = id_tg
        elif id_max is not None and cur_id_max is None:
            conn.execute("UPDATE Users SET id_max = ? WHERE id_tg = ?", (id_max, cur_id_tg))
            cur_id_max = id_max

        # Обновление профильных полей у найденной записи
        updates, params = [], []
        if username:
            updates.append("username = ?")
            params.append(username)
        if first_name:
            updates.append("first_name = ?")
            params.append(first_name)
        if gender:
            updates.append("gender = ?")
            params.append(gender)
        if updates:
            if cur_id_tg is not None:
                where, where_val = "id_tg", cur_id_tg
            else:
                where, where_val = "id_max", cur_id_max
            params.append(where_val)
            conn.execute(
                f"UPDATE Users SET {', '.join(updates)} WHERE {where} = ?",
                tuple(params),
            )
        conn.commit()
        print(f"User updated in the database: id_tg={cur_id_tg}, id_max={cur_id_max}.")
    except sqlite3.Error as e:
        print(f"Error adding user to database: {e}")
    finally:
        conn.close()


# Функция вывода пользователей
def show_users():
    """Список пользователей для админ-панелей обоих ботов."""
    conn = create_connection()
    if conn is None:
        return ""
    try:
        users_list = conn.execute(
            "SELECT id_tg, id_max, username, first_name FROM Users ORDER BY rowid"
        )
        message = ""
        for id_tg, id_max, username, first_name in users_list:
            tg_part = f"TG: {id_tg}" if id_tg is not None else "TG: —"
            max_part = f"MAX: {id_max}" if id_max is not None else "MAX: —"
            uname = f" @{username}" if username else ""
            message += f"{tg_part} | {max_part}{uname} {first_name or ''}\n"
        return message
    finally:
        conn.close()


# Создаём функцию
def show_statistics():
    conn = create_connection()
    if conn is None:
        return 0
    try:
        count_users = conn.execute("SELECT COUNT(*) FROM Users").fetchone()
        return count_users[0]
    finally:
        conn.close()


def _set_block(input_id, value):
    """Ставит/снимает блокировку по id любого из мессенджеров.

    Возвращает True, если запись найдена и изменена.
    """
    try:
        input_id = int(str(input_id).strip())
    except (TypeError, ValueError):
        return False
    conn = create_connection()
    if conn is None:
        return False
    try:
        cur = conn.execute(
            "UPDATE Users SET block = ? WHERE id_tg = ? OR id_max = ?",
            (value, input_id, input_id),
        )
        conn.commit()
        return cur.rowcount > 0
    except sqlite3.Error as e:
        print(f"Ошибка блокировки пользователя: {e}")
        return False
    finally:
        conn.close()


# Функция блокировки пользователей
def add_user_to_block(input_id):
    """Блокирует пользователя по TG- или MAX-id. Возвращает True, если успех."""
    return _set_block(input_id, 1)


# Функция для проверки пользователя на нахождение в блокировке
def check_user_in_block(id_tg=None, id_max=None):
    """Проверяет, заблокирован ли пользователь по любому из известных id."""
    if id_tg is None and id_max is None:
        return False
    conn = create_connection()
    if conn is None:
        return False
    try:
        row = _find(conn, id_tg, id_max)
    except sqlite3.Error as e:
        print(f"Ошибка базы данных: {e}")
        return False
    finally:
        conn.close()
    if row:
        return bool(row[5])  # столбец block
    return False  # если пользователя нет в таблице — считаем не заблокированным


# Функция для разблокировки пользователей
def unlock_users(input_id):
    """Разблокирует пользователя по TG- или MAX-id. Возвращает True, если успех."""
    return _set_block(input_id, 0)


def gender(id_tg=None, id_max=None):
    """Возвращает пол пользователя по любому из id (или None)."""
    if id_tg is None and id_max is None:
        return None
    conn = create_connection()
    if conn is None:
        return None
    try:
        row = _find(conn, id_tg, id_max)
    finally:
        conn.close()
    if row:
        return row[4]  # столбец gender
    print(f"Пользователь с id_tg={id_tg}, id_max={id_max} не найден в таблице Users")
    return None
