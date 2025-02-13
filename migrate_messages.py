import os
import json
import time
from data import db_session
from data.tickets import Ticket


def migrate_messages():
    # Инициализируем базу данных
    db_session.global_init("db/vocord.sqlite")
    db_sess = db_session.create_session()

    # Получаем все тикеты для сопоставления chat_id и имен
    tickets = {
        str(ticket.id): ticket for ticket in db_sess.query(Ticket).all()}

    # Перебираем все файлы в директории messages
    messages_dir = 'messages'
    for filename in os.listdir(messages_dir):
        if filename.endswith('data.json'):
            ticket_id = filename.replace('data.json', '')
            filepath = os.path.join(messages_dir, filename)

            print(f"Обрабатываем файл: {filename}")

            try:
                # Читаем старый формат
                with open(filepath, 'r') as f:
                    old_data = json.load(f)

                # Создаем новую структуру
                new_messages = []

                if 'data' in old_data:
                    ticket = tickets.get(ticket_id)
                    if ticket:
                        for msg in old_data['data']:
                            # Старый формат: [номер, текст, тип(0/1), message_id]
                            new_message = {
                                "message_id": msg[3],
                                "text": msg[1],
                                "sender_type": "client" if msg[2] == 1 else "support",
                                "sender_name": ticket.name if msg[2] == 1 else "Техподдержка",
                                # Используем текущее время, так как старые сообщения не содержат временную метку
                                "timestamp": int(time.time())
                            }
                            new_messages.append(new_message)

                # Сохраняем в новом формате
                new_data = {"messages": new_messages}
                with open(filepath, 'w') as f:
                    json.dump(new_data, f, indent=2)

                print(f"Файл {filename} успешно обновлен")

            except Exception as e:
                print(f"Ошибка при обработке файла {filename}: {e}")

    db_sess.close()


if __name__ == "__main__":
    migrate_messages()
