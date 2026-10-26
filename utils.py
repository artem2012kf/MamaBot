import sqlite3
import active
from shared.db import configure_connection, DB_TIMEOUT

# Долгоживущее соединение этого процесса. Telegram-бот и MAX-бот работают
# двумя отдельными процессами с этой же файловой базой, поэтому соединение
# настраивается через configure_connection(): WAL + busy_timeout снимают
# блокировки "database is locked" при одновременных записях.
connection = configure_connection(sqlite3.connect('sbor.db', timeout=DB_TIMEOUT))
cursor = connection.cursor()

cursor.execute(''' 
CREATE TABLE IF NOT EXISTS sbor(
name TEXT NOT NULL, 
gender TEXT NOT NULL
)
''')

def _read(sql, params=()):
    """Выполняет SELECT новым коротким соединением.

    Telegram-бот и MAX-бот пишут в одну базу из разных процессов; чтение
    через свежее соединение гарантирует актуальный снимок данных (WAL) и
    не мешает параллельной записи.
    """
    conn = sqlite3.connect('sbor.db', timeout=DB_TIMEOUT)
    configure_connection(conn)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def usersdel():
    cursor.execute("DELETE FROM sbor")
    connection.commit()

def check_user_exists(username):
    try:
        result = _read("SELECT name FROM sbor WHERE name = ?", (username,))
        return bool(result)
    except Exception as e:
        print(f"Ошибка при проверке пользователя: {e}")
        return False

def del_one(username):
    cursor.execute("DELETE FROM sbor WHERE name = ?", (username,))
    connection.commit()
    print(f"Удален пользователь: {username}")

def add(username, gender):
    if gender is None:
        gender = "unknown"
        print(f"Внимание: для пользователя {username} gender = None, установлено 'unknown'")
    
    cursor.execute("INSERT INTO sbor (name, gender) VALUES (?, ?)", 
                  (username, gender))
    connection.commit()
    print(f"Добавлен: {username}, gender: {gender}")

def delete(username):
    cursor.execute('DELETE FROM sbor WHERE name = ?', (username,))
    connection.commit()

def delete_user_friends(user_name):
    """Удалить всех друзей пользователя"""
    cursor.execute("DELETE FROM sbor WHERE name LIKE ?", (f"{user_name} +%",))
    connection.commit()
    print(f"Удалены все друзья пользователя {user_name}")

def get_user_friends_count(user_name, gender_type):
    """Получить количество друзей определенного пола у пользователя"""
    friend_name = get_user_friend_name(user_name, gender_type)
    row = _read("SELECT COUNT(*) FROM sbor WHERE name = ? AND gender = ?",
                (friend_name, gender_type))
    return row[0][0]

def select():
    # Получаем все записи в порядке добавления (свежее чтение — список
    # может меняться и из Telegram-бота, и из MAX-бота)
    results = _read('SELECT name, gender FROM sbor ORDER BY rowid')

    if not results:
        return 'Список пуст'

    all_entries = results
    
    # Разделяем на основные (первые 12) и резерв
    main_list = all_entries[:12]
    reserve_list = all_entries[12:]
    
    total_count = len(all_entries)
    main_count = len(main_list)
    
    # Считаем статистику М/Ж только для ОСНОВНОГО состава (первые 12)
    men_count = 0
    women_count = 0
    
    for row in main_list:
        if row[1] in ['М', 'мужской', 'male', 'м', 'Муж', ' Муж']:
            men_count += 1
        elif row[1] in ['Ж', 'женский', 'female', 'ж', 'Дев', ' Дев']:
            women_count += 1
    
    # ИЗМЕНЕНО: Добавлено жирное форматирование для количества
    sms = f'Записано: *{main_count}*\n'
    sms += f'М - {men_count}\nД - {women_count}\n --------- \n'
    
    # Выводим основной состав в порядке добавления
    for i, row in enumerate(main_list, 1):
        name = row[0]
        # Добавляем + к друзьям с пробелом и сокращаем названия
        if '(' in name and ')' in name:
            # Заменяем "Муж (" на "+ М (", "Дев (" на "+ Д ("
            if name.startswith('Муж ('):
                name = name.replace('Муж (', '+ М (')
            elif name.startswith('Дев ('):
                name = name.replace('Дев (', '+ Д (')
        sms += f'{i}. {name}\n'
    
    # Выводим резерв если есть
    if reserve_list:
        sms += '\nРезерв:\n'
        for i, row in enumerate(reserve_list, len(main_list) + 1):
            name = row[0]
            # Добавляем + к друзьям в резерве с пробелом и сокращаем названия
            if '(' in name and ')' in name:
                if name.startswith('Муж ('):
                    name = name.replace('Муж (', '+ М (')
                elif name.startswith('Дев ('):
                    name = name.replace('Дев (', '+ Д (')
            sms += f'{i}. {name}\n'

    return sms

def nomer():
    results = _read('SELECT name FROM sbor')
    return len(results)

def count_women():
    # Считаем только основных участников (не друзей) - тех, у кого в имени нет скобок
    row = _read("SELECT COUNT(*) FROM sbor WHERE gender IN ('Ж', 'женский', 'female', 'ж', 'Дев', ' Дев') AND name NOT LIKE '%(%' AND name NOT LIKE '%)%'")
    return row[0][0]
def get_user_friend_name(user_name, gender_type):
    """Генерирует имя друга"""
    return f"{gender_type} ({user_name})"

def check_friend_exists(user_name, gender_type):
    """Проверяет, существует ли хотя бы один друг определенного пола у пользователя"""
    friend_name = get_user_friend_name(user_name, gender_type)
    row = _read("SELECT COUNT(*) FROM sbor WHERE name = ? AND gender = ?",
                (friend_name, gender_type))
    return row[0][0] > 0
def get_next_friend_number(user_name, gender_type):
    """Получить следующий номер для друга пользователя"""
    results = _read("SELECT name FROM sbor WHERE name LIKE ? AND gender = ?",
                    (f"{user_name} +{gender_type}%", gender_type))
    
    if not results:
        return 1
    
    # Находим максимальный номер
    max_number = 0
    for result in results:
        name = result[0]
        parts = name.split('+')
        if len(parts) > 1:
            number_part = parts[1].replace(gender_type, '')
            if number_part.isdigit():
                max_number = max(max_number, int(number_part))
            else:
                max_number = max(max_number, 1)
    
    return max_number + 1
def delete_one_friend(user_name, gender_type):
    """Удаляет ОДНУ запись друга определенного пола пользователя"""
    friend_name = get_user_friend_name(user_name, gender_type)
    
    # Находим первую запись для удаления (свежее чтение — второй бот мог
    # уже удалить эту запись параллельно)
    result = _read("SELECT rowid FROM sbor WHERE name = ? AND gender = ? LIMIT 1",
                   (friend_name, gender_type))
    
    if result:
        rowid_to_delete = result[0][0]
        # Удаляем запись по rowid
        cursor.execute("DELETE FROM sbor WHERE rowid = ?", (rowid_to_delete,))
        connection.commit()
        print(f"Удален один {gender_type}: {friend_name}")
        return True
    else:
        print(f"Не найдено записей для удаления: {friend_name}")
        return False

def find_user_by_name(name):
    """Ищет существующего пользователя по имени (first_name из MAX).

    В MAX нет юзернеймов, поэтому при регистрации бот ищет человека по
    полному имени среди уже записанных через Telegram. Сличение регистронезависимое.

    Возвращает tuple строки Users или None.
    """
    if not name:
        return None
    conn = active.create_connection()
    if conn is None:
        return None
    try:
        rows = conn.execute(
            "SELECT id_tg, id_max, username, first_name FROM Users"
        ).fetchall()
    finally:
        conn.close()
    target = str(name).strip().casefold()
    for row in rows:
        if row[3] and str(row[3]).strip().casefold() == target:
            return row
    return None
