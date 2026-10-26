import sqlite3

# Сколько секунд ждать освобождения блокировки БД, прежде чем выдать
# "database is locked". Оба бота (Telegram и MAX) работают ДВУМЯ ПРОЦЕССАМИ
# с одними и теми же файлами sbor.db / database.db, поэтому записи иногда
# пересекаются по времени.
DB_TIMEOUT = 30


def configure_connection(conn: sqlite3.Connection) -> sqlite3.Connection:
    """Переводит соединение в режим, безопасный для двух процессов.

    WAL (write-ahead logging) позволяет одному процессу читать базу,
    пока другой в это время пишет в неё, и заметно снижает вероятность
    блокировок при конкурентном доступе Telegram-бота и MAX-бота.
    """
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=%d" % (DB_TIMEOUT * 1000))
    return conn


def get_connection(db_name: str):
    """Return a SQLite connection to the specified database file.
    The caller is responsible for closing the connection when done.
    """
    return configure_connection(
        sqlite3.connect(db_name, timeout=DB_TIMEOUT)
    )
