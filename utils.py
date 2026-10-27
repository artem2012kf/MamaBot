import sqlite3
import active

connection = sqlite3.connect('sbor.db', timeout=15)
# WAL-режим: одновременный доступ двух процессов (TG и MAX) без взаимных блокировок
try:
    connection.execute("PRAGMA journal_mode=WAL")
except sqlite3.OperationalError:
    pass
connection.execute("PRAGMA busy_timeout=15000")
cursor = connection.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS sbor(
name TEXT NOT NULL,
gender TEXT NOT NULL
)
''')

def usersdel():
    cursor.execute("DELETE FROM sbor")
    connection.commit()

def check_user_exists(username):
    try:
        cursor.execute("SELECT name FROM sbor WHERE name = ?", (username,))
        result = cursor.fetchall()  # дочитываем курсор, чтобы не держать блокировку чтения
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
    cursor.execute("SELECT COUNT(*) FROM sbor WHERE name = ? AND gender = ?",
                  (friend_name, gender_type))
    return cursor.fetchall()[0][0]

def select():
    # Получаем все записи в порядке добавления
    cursor.execute('SELECT name, gender FROM sbor ORDER BY rowid')
    results = cursor.fetchall()

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
    cursor.execute('SELECT name FROM sbor')
    results = cursor.fetchall()
    return len(results)

def count_women():
    # Считаем только основных участников (не друзей) - тех, у кого в имени нет скобок
    cursor.execute("SELECT COUNT(*) FROM sbor WHERE gender IN ('Ж', 'женский', 'female', 'ж', 'Дев', ' Дев') AND name NOT LIKE '%(%' AND name NOT LIKE '%)%'")
    return cursor.fetchone()[0]
def get_user_friend_name(user_name, gender_type):
    """Генерирует имя друга"""
    return f"{gender_type} ({user_name})"

def check_friend_exists(user_name, gender_type):
    """Проверяет, существует ли хотя бы один друг определенного пола у пользователя"""
    friend_name = get_user_friend_name(user_name, gender_type)
    cursor.execute("SELECT COUNT(*) FROM sbor WHERE name = ? AND gender = ?",
                  (friend_name, gender_type))
    return cursor.fetchall()[0][0] > 0
def get_next_friend_number(user_name, gender_type):
    """Получить следующий номер для друга пользователя"""
    cursor.execute("SELECT name FROM sbor WHERE name LIKE ? AND gender = ?", 
                  (f"{user_name} +{gender_type}%", gender_type))
    results = cursor.fetchall()
    
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
    
    # Находим первую запись для удаления
    cursor.execute("SELECT rowid FROM sbor WHERE name = ? AND gender = ? LIMIT 1", 
                  (friend_name, gender_type))
    result = cursor.fetchone()
    
    if result:
        rowid_to_delete = result[0]
        # Удаляем запись по rowid
        cursor.execute("DELETE FROM sbor WHERE rowid = ?", (rowid_to_delete,))
        connection.commit()
        print(f"Удален один {gender_type}: {friend_name}")
        return True
    else:
        print(f"Не найдено записей для удаления: {friend_name}")
        return False