import sqlite3
import time

DATABASE_NAME = "database.db"


def _configure_connection(conn):
    """WAL-режим и таймаут для одновременного доступа двух процессов (TG и MAX).

    В WAL читатели не блокируют писателей и наоборот — это устраняет
    «database is locked», к которому приводит долгий shared-lock в journal-режиме
    delete. WAL персистентен: выставляется один раз на файл базы.
    """
    conn.execute("PRAGMA busy_timeout=15000")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        # Другой процесс держит базу — WAL уже включён им или включится позже
        pass
    return conn


# Создание базы данных, если она не была создана ранее
connection = sqlite3.connect('database.db', timeout=15)
_configure_connection(connection)
cursor = connection.cursor()

NEW_SCHEMA = """CREATE TABLE IF NOT EXISTS Users(
id_tg INT,
id_max INT,
username TEXT,
first_name_tg TEXT,
first_name_max TEXT,
gender TEXT,
block INT
); """


def create_connection():
    """Создает соединение с базой данных SQLite."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME, timeout=15)
        _configure_connection(conn)
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to the database: {e}")
    return conn


def _table_columns(cur, table):
    """Список столбцов таблицы."""
    return [row[1] for row in cur.execute(f"PRAGMA table_info({table})")]


def _migrate_users_table():
    """Однократная миграция схемы Users. Поддерживает оба предыдущих варианта:
    - Users(id, username, first_name, ...) -> id переименовывается в id_tg, добавляются id_max, first_name_tg/first_name_max
    - Users(id_tg, id_max, username, first_name, ...) -> first_name разделяется на first_name_tg/first_name_max

    Запускается при импорте модуля обоими ботами. Если база заблокирована другим
    процессом (например, открыта в DB Browser), миграция откладывается до
    следующего запуска — бот продолжает работу.
    """
    conn = sqlite3.connect(DATABASE_NAME, timeout=15, isolation_level=None)
    _configure_connection(conn)
    try:
        cur = conn.cursor()
        # Быстрая проверка без транзакции: возможно, мигрировать нечего
        cols = _table_columns(cur, "Users")
        if "id_tg" in cols and "id_max" in cols and "first_name_tg" in cols and "first_name_max" in cols:
            return

        # Миграция нужна — берём блокировку записи с повторами
        locked = False
        for _ in range(3):
            try:
                cur.execute("BEGIN IMMEDIATE")
                break
            except sqlite3.OperationalError as e:
                print(f"Миграция Users: база заблокирована ({e}), повтор через 3 с...")
                time.sleep(3)
        else:
            print("Миграция Users пропущена: база заблокирована другим процессом "
                  "(например, открыта в DB Browser). Будет выполнена при следующем запуске.")
            return

        try:
            cols = _table_columns(cur, "Users")
            if "id_tg" in cols and "id_max" in cols and "first_name_tg" in cols and "first_name_max" in cols:
                cur.execute("COMMIT")
                return
            if "id_tg" in cols and "first_name" in cols:
                # Промежуточная схема: разделяем first_name на два столбца
                cur.execute("ALTER TABLE Users RENAME TO Users_old")
                cur.execute(NEW_SCHEMA)
                cur.execute(
                    "INSERT INTO Users (id_tg, id_max, username, first_name_tg, first_name_max, gender, block) "
                    "SELECT id_tg, id_max, username, first_name, NULL, gender, block FROM Users_old"
                )
                cur.execute("DROP TABLE Users_old")
                print("База Users мигрирована: first_name -> first_name_tg, добавлен first_name_max")
            elif "id" in cols:
                # Самая старая схема: переименовываем id -> id_tg и добавляем новые столбцы
                cur.execute("ALTER TABLE Users RENAME TO Users_old")
                cur.execute(NEW_SCHEMA)
                cur.execute(
                    "INSERT INTO Users (id_tg, id_max, username, first_name_tg, first_name_max, gender, block) "
                    "SELECT id, NULL, username, first_name, NULL, gender, block FROM Users_old"
                )
                cur.execute("DROP TABLE Users_old")
                print("База Users мигрирована: id -> id_tg, добавлены столбцы id_max, first_name_tg, first_name_max")
            else:
                # Свежая база — просто создаём таблицу новой схемы
                cur.execute(NEW_SCHEMA)
            cur.execute("COMMIT")
        except Exception:
            try:
                cur.execute("ROLLBACK")
            except sqlite3.OperationalError:
                pass
            raise
    finally:
        conn.close()


_migrate_users_table()
cursor.execute(NEW_SCHEMA)
connection.commit()


#Создаём функцию в которую передаём user_id, username, first_name
def add_user(user_id, username, first_name, gender, source="tg"):
    """Добавляет пользователя в базу данных, если его там нет.

    source="tg" — ID пишется в id_tg, имя в first_name_tg;
    source="max" — в id_max и first_name_max (username в MAX отсутствует).
    """
    if source == "tg":
        id_col, name_col = "id_tg", "first_name_tg"
    else:
        id_col, name_col = "id_max", "first_name_max"
    conn = create_connection()
    if conn is not None:
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT {id_col} FROM Users WHERE {id_col} = ?", (user_id,))
            existing_user = cur.fetchone()

            if not existing_user:
                cur.execute(
                    "INSERT INTO Users (id_tg, id_max, username, first_name_tg, first_name_max, gender, block) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_id if source == "tg" else None,
                     user_id if source == "max" else None,
                     username,
                     first_name if source == "tg" else None,
                     first_name if source == "max" else None,
                     gender, 0),
                )
                conn.commit()
                print(f"User {user_id} ({source}) added to the database.")
            else:
                print(f"User {user_id} already exists in the database.")
        except sqlite3.Error as e:
            print(f"Error adding user to database: {e}")
        finally:
            conn.close()


# Функция вывода пользователей
def show_users():
    #Выводим оба идентификатора с именами: TG и MAX (у кого-то может не быть одного из них)
    users_list = cursor.execute('SELECT id_tg, id_max, username, first_name_tg, first_name_max FROM Users')

    message = ""
    for id_tg, id_max, username, first_name_tg, first_name_max in users_list:
        uname = f"@{username}" if username else "-"
        tg = f"{id_tg} ({first_name_tg})" if id_tg is not None else "-"
        mx = f"{id_max} ({first_name_max})" if id_max is not None else "-"
        message += f"TG: {tg} | MAX: {mx} | {uname}\n"

    return message


#Создаём функцию
def show_statistics():
    #Получаем список в котором записано количество элементов первого столбца таблицы
    # fetchall() дочитывает курсор: незакрытый SELECT держит транзакцию чтения
    count_users = cursor.execute("SELECT COUNT(*) FROM Users").fetchall()

    #Возвращаем значение для отправки
    return count_users[0][0]


#Функция блокировки пользователей
def add_user_to_block(input_id):
    """Блокирует пользователя по ID (подходит как TG-, так и MAX-идентификатор)."""
    cursor.execute('UPDATE Users SET block = ? WHERE id_tg = ? OR id_max = ?', (1, input_id, input_id))
    connection.commit()


#Функция для проверки пользователя на нахождение в блокировке
def check_user_in_block(user_id, source="tg"):
    """
    Проверяет, заблокирован ли пользователь.

    Args:
        user_id (int): ID пользователя (Telegram или MAX).
        source (str): "tg" или "max" — по какому столбцу искать.

    Returns:
        bool: True, если пользователь заблокирован, False в противном случае.
    """
    id_col = "id_tg" if source == "tg" else "id_max"
    try:
        # fetchall() дочитывает курсор, чтобы не держать транзакцию чтения
        cursor.execute(f'SELECT block FROM Users WHERE {id_col} = ?', (user_id,))
        user_data = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Ошибка базы данных: {e}")
        return False  # Обработка ошибки, можно вернуть False по умолчанию
    if user_data:
        block_status = user_data[0][0]
        return bool(block_status)  # Возвращаем bool(1) = True или bool(0) = False
    return False  # Если пользователя нет в таблице, считаем, что он не заблокирован


#Функция для разблокировки пользователей
def unlock_users(input_id):
    """Разблокирует пользователя по ID (подходит как TG-, так и MAX-идентификатор)."""
    cursor.execute('UPDATE Users SET block = ? WHERE id_tg = ? OR id_max = ?', (0, input_id, input_id))
    connection.commit()


def gender(user_id, source="tg"):
    """Возвращает пол пользователя по его TG- или MAX-идентификатору."""
    id_col = "id_tg" if source == "tg" else "id_max"
    cursor.execute(f"SELECT gender FROM Users WHERE {id_col} = ?", (user_id,))
    result = cursor.fetchall()  # дочитываем курсор, чтобы не держать блокировку чтения
    if result:
        return result[0][0]  # Возвращаем значение gender из основной базы
    else:
        print(f"Пользователь с id {user_id} ({source}) не найден в таблице Users")
        return None
