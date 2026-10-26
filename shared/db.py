import sqlite3

def get_connection(db_name: str):
    """Return a SQLite connection to the specified database file.
    The caller is responsible for closing the connection when done.
    """
    return sqlite3.connect(db_name)
