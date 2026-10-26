import sqlite3
# Создание базы данных, если она не была создана ранее
connection = sqlite3.connect('database.db')
cursor = connection.cursor()
DATABASE_NAME = "database.db"
def create_connection():
    """Создает соединение с базой данных SQLite."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to the database: {e}")
    return conn
#Создание таблицы Users в нутри базы данных database
cursor.execute("""CREATE TABLE IF NOT EXISTS Users(id INT, username TEXT, first_name TEXT, gender TEXT, block INT); """)
#Создаём функцию в которую передаём user_id, username, first_name
def add_user(user_id, username, first_name, gender):
    """Добавляет пользователя в базу данных, если его там нет."""
    conn = create_connection()
    if conn is not None:
        try:
            cursor = conn.cursor()
            # ПРОВЕРКА ПО ID, А НЕ ПО user_id
            cursor.execute("SELECT id FROM Users WHERE id = ?", (user_id,))
            existing_user = cursor.fetchone()

            if not existing_user:
                # Добавление данных с правильным количеством столбцов
                cursor.execute("INSERT INTO Users (id, username, first_name, gender, block) VALUES (?, ?, ?, ?, ?)",
                               (user_id, username, first_name, gender, 0))
                conn.commit()
                print(f"User {user_id} added to the database.")
            else:
                print(f"User {user_id} already exists in the database.")
        except sqlite3.Error as e:
            print(f"Error adding user to database: {e}")
        finally:
            conn.close()

    # Не нужно здесь commit, он уже в add_user
    # connection.commit()


# Функция вывода пользователей
def show_users():

    #Получаем все столбцы из таблицы в список users_list
    users_list = cursor.execute('SELECT * FROM Users')

    #Создаём переменную в которую будем записывать user_id, username, first_name пользователей
    message = ""

    #Проходимся по элементам списка и записываем их в переменную message
    for users in users_list:
        message += f"{users[0]} @{users[1]} {users[2]}\n"

    #Обновляем соединение с таблицей
    connection.commit()

    #Возвращаем переменную, которая будет служить сообщением для отправки при нажатии на кнопку
    return message
#Создаём функцию
def show_statistics():

    #Получаем список в котором записано количество элементов первого столбца таблицы
    count_users = cursor.execute("SELECT COUNT(*) FROM Users").fetchone()

    #Обновляем соединение с таблицей
    connection.commit()

    #Возвращаем значение для отправки
    return count_users[0]
#Функция блокировки пользователей
def add_user_to_block(input_id):

    #Обновляем 0 на 1
    cursor.execute(f'UPDATE Users SET block = ? WHERE id = ?', (1, input_id))

    #Обновляем соединение с таблицей
    connection.commit()
#Функция для проверки пользователя на нахождение в блокировке
#Функция для проверки пользователя на нахождение в блокировке
def check_user_in_block(user_id):
    """
    Проверяет, заблокирован ли пользователь.

    Args:
        user_id (int): ID пользователя.

    Returns:
        bool: True, если пользователь заблокирован, False в противном случае.
    """
    try:
      cursor.execute(f'SELECT block FROM Users WHERE id = {user_id}')
      user_data = cursor.fetchone()
    except sqlite3.Error as e:
      print(f"Ошибка базы данных: {e}")
      return False # Обработка ошибки, можно вернуть False по умолчанию
    if user_data:
        block_status = user_data[0]
        return bool(block_status) # Возвращаем bool(1) = True или bool(0) = False
    return False # Если пользователя нет в таблице, считаем, что он не заблокирован


#Функция для разблокировки пользователей
def unlock_users(input_id):
    
    # Обновляем 1 на 0
    cursor.execute(f'UPDATE Users SET block = ? WHERE id = ?', (0, input_id))

    #Обновляем соединение с таблицей
    connection.commit()
def gender(user_id):
    cursor.execute("SELECT gender FROM Users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        return result[0]  # Возвращаем значение gender из основной базы
    else:
        print(f"Пользователь с id {user_id} не найден в таблице Users")
        return None