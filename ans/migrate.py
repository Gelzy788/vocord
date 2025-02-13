from data import db_session
import sqlite3


def migrate():
    """Добавляет столбец assigned_to в таблицу tickets"""
    # Подключаемся к базе данных
    conn = sqlite3.connect('db/vocord.sqlite')
    cursor = conn.cursor()

    try:
        # Добавляем новую колонку
        cursor.execute('''
            ALTER TABLE tickets 
            ADD COLUMN assigned_to INTEGER 
            REFERENCES users(id)
        ''')
        print("Колонка assigned_to успешно добавлена")

        conn.commit()
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Колонка assigned_to уже существует")
        else:
            print(f"Ошибка при добавлении колонки: {e}")
    finally:
        conn.close()


if __name__ == '__main__':
    # Инициализируем соединение с базой данных
    db_session.global_init("db/vocord.sqlite")
    migrate()
