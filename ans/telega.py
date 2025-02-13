import logging
from telegram import Update, ReplyKeyboardMarkup
from requests import get, post
# import telebot
# bot = telebot.TeleBot('6874396479:AAETyIiiUhpR-pJlW7cwcX0Sd59yDI8jqVc')
import re
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
import os
import json
import time
import signal
import sys

data = []
chat_id = ''

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO  # Изменим уровень логирования на INFO
)
logger = logging.getLogger(__name__)

# Создаем файл для хранения PID
PID_FILE = "bot.pid"


def cleanup():
    """Очистка при выходе"""
    try:
        os.remove(PID_FILE)
    except OSError:
        pass


def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    cleanup()
    sys.exit(0)


def check_running():
    """Проверяет, не запущен ли уже бот"""
    if os.path.exists(PID_FILE):
        with open(PID_FILE, 'r') as f:
            old_pid = int(f.read())
        try:
            # Проверяем, существует ли процесс
            os.kill(old_pid, 0)
            print(f"Бот уже запущен (PID: {old_pid})")
            sys.exit(1)
        except OSError:
            # Процесс не существует
            pass

    # Записываем текущий PID
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))


reply_keyboard = [['Да', 'Нет']]
product_list = [['VOCORD MicroCyclops', 'VOCORD Cyclops', 'VOCORD Cyclops Portable'],
                ['VOCORD SSCross', 'VOCORD SMCross', 'VOCORD NCCross'],
                ['VOCORD VERelay 6', 'VOCORD TLCross'],
                ['Комплекс освещения VOCORD'],
                ['VOCORD Tahion', 'VOCORD ParkingControl']]
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
pmarkup = ReplyKeyboardMarkup(product_list, one_time_keyboard=True)


def check_email(email):
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    if re.match(pattern, email):
        return True
    else:
        return False


async def start(update, context):
    """Начало создания нового тикета"""
    # Очищаем предыдущие данные и сбрасываем состояние
    context.user_data.clear()
    global data, chat_id
    data = []
    chat_id = str(update.message.chat.id)  # Устанавливаем новый chat_id

    await update.message.reply_text(
        "Здравствуйте. Я - бот для техподдержки Вокорда!\n"
        "Вы можете прислать нам прислать описание вашей проблемы и мы в скором времени свяжемся с вами!\n"
        "Если вы передумали или ваша проблема была устранена нажмите /stop."
        "Для связи с вами нам нужно знать как к вам обращаться!\n"
        "Как к вам обращаться? (Напишите в формате ФИО с пробелами)")
    return 1


async def first_response(update, context):
    global data, chat_id
    chat_id = str(update.message.chat.id)
    print(f"Chat ID: {chat_id}")
    data.append(update.message.text)
    logger.info(data[-1])

    # Очищаем предыдущие данные о тикетах
    context.user_data.clear()

    # Получаем все тикеты пользователя
    ticket_response = get(
        f'http://127.0.0.1:8080/api/ticket_by_chat/{chat_id}').json()

    # Если есть тикет, закрываем его
    if ticket_response.get('ticket'):
        post(
            f'http://127.0.0.1:8080/api/close_ticket/{ticket_response["ticket"]["id"]}')

    await update.message.reply_text(
        f"Для связи мы используем почту.\n"
        f"(Пришлите адрес почты для ответа Вам. В почте обязан присутствовать символ '@')")
    return 2


async def second_response(update, context):
    global data
    data.append(update.message.text)
    logger.info(data[-1])
    if not check_email(email=data[-1]):
        await update.message.reply_text("Некорректная почта! Введите почту еще раз!")
        del data[-1]
        return 2
    await update.message.reply_text("Пришлите название нашего продукта или выберите из списка,"
                                    " проблему о котором вы хотите задать!",
                                    reply_markup=pmarkup)
    return 3


async def third_response(update, context):
    global data
    data.append(update.message.text)
    logger.info(data[-1])
    await update.message.reply_text("Опишите проблему кратко!")
    return 4


async def fourth_response(update, context):
    global data
    data.append(update.message.text)
    logger.info(data[-1])
    await update.message.reply_text("Опишите проблему подробно!")
    return 5


async def fifth_response(update, context):
    global data, chat_id
    data.append(update.message.text)
    logger.info(data[-1])

    current_chat_id = str(update.message.chat.id)  # Получаем текущий chat_id

    # Закрываем все предыдущие тикеты пользователя
    ticket_response = get(
        f'http://127.0.0.1:8080/api/ticket_by_chat/{current_chat_id}').json()
    if ticket_response.get('ticket'):
        post(
            f'http://127.0.0.1:8080/api/delete_ticket/{ticket_response["ticket"]["id"]}')

    await update.message.reply_text(
        "Спасибо за отзыв!\n"
        "Мы постараемся решить вашу проблему как можно быстрее.\n"
        "Теперь вы можете отправлять сообщения прямо в чат или использовать команду /message, например:\n"
        "/message У меня появился еще один вопрос")

    # Создаем новый тикет
    response = post('http://127.0.0.1:8080/api/add_ticket',
                    json={'name': data[0],
                          'email': data[1],
                          'product_name': data[2],
                          'problem_name': data[3],
                          'problem_full': data[4],
                          'is_finished': False,
                          'worker': 'Не назначен',
                          'chat_id': current_chat_id,
                          'last_id': update.message.id
                          }
                    )

    # Очищаем старые данные и обновляем chat_id
    data = []
    chat_id = current_chat_id

    # Переходим в режим чата
    return 6  # Возвращаем состояние чата вместо END


async def handle_chat_message(update, context):
    """Обработчик сообщений в режиме чата"""
    message_text = update.message.text
    chat_id = str(update.message.chat.id)
    message_id = update.message.message_id

    print(f"Получено новое сообщение: {message_text} от chat_id: {chat_id}")

    # Получаем тикет по chat_id
    ticket_response = get(
        f'http://127.0.0.1:8080/api/ticket_by_chat/{chat_id}').json()

    print(f"Ответ API ticket_by_chat: {ticket_response}")

    if not ticket_response.get('ticket'):
        await update.message.reply_text(
            "У вас нет активного тикета. Создайте новый тикет с помощью команды /send_request")
        context.user_data.clear()
        return ConversationHandler.END

    ticket = ticket_response['ticket']
    print(f"Найден тикет: {ticket}")

    # Проверяем, не закрыт ли тикет
    if ticket.get('is_finished'):
        await update.message.reply_text(
            "Этот тикет уже закрыт. Если у вас появились новые вопросы, создайте новый тикет командой /send_request")
        context.user_data.clear()
        return ConversationHandler.END

    # Создаем директорию для сообщений, если её нет
    messages_dir = os.path.join(os.path.dirname(__file__), 'messages')
    if not os.path.exists(messages_dir):
        try:
            os.makedirs(messages_dir)
            print(f"Создана директория: {messages_dir}")
        except Exception as e:
            print(f"Ошибка при создании директории: {e}")
            await update.message.reply_text("Произошла ошибка при сохранении сообщения")
            return 6

    filename = os.path.join(messages_dir, f'{ticket["id"]}data.json')
    print(f"Путь к файлу сообщений: {filename}")

    message_data = {
        "message_id": message_id,
        "text": message_text,
        "sender_type": "client",
        "sender_name": ticket["name"],
        "timestamp": int(time.time())
    }

    try:
        # Читаем существующие сообщения или создаем новый список
        if os.path.exists(filename):
            with open(filename, "r", encoding='utf-8') as json_file:
                data = json.load(json_file)
                print(f"Прочитаны существующие сообщения: {data}")
        else:
            data = {"messages": []}
            print("Создан новый список сообщений")

        # Добавляем новое сообщение, если его еще нет
        if not any(msg.get("message_id") == message_id for msg in data["messages"]):
            data["messages"].append(message_data)
            print(f"Добавлено новое сообщение: {message_data}")

            # Сохраняем обновленные данные
            with open(filename, "w", encoding='utf-8') as json_file:
                json.dump(data, json_file, indent=2, ensure_ascii=False)
                print(f"Файл успешно сохранен: {filename}")

    except Exception as e:
        print(f"Ошибка при работе с файлом: {e}")
        await update.message.reply_text("Произошла ошибка при сохранении сообщения")
        return 6

    # Обновляем last_id в тикете
    try:
        response = post('http://127.0.0.1:8080/api/update_last_id',
                        json={'ticket_id': ticket['id'], 'last_id': message_id})
        print(f"Ответ API update_last_id: {response.json()}")
    except Exception as e:
        print(f"Ошибка при обновлении last_id: {e}")

    await update.message.reply_text("Ваше сообщение отправлено в техподдержку")
    return 6


async def stop(update, context):
    """Обработчик команды /stop"""
    global data, chat_id
    current_chat_id = str(update.message.chat.id)
    print(f"Получена команда /stop от chat_id: {current_chat_id}")

    # Получаем тикет по chat_id
    ticket_response = get(
        f'http://127.0.0.1:8080/api/ticket_by_chat/{current_chat_id}').json()
    print(f"Ответ API ticket_by_chat: {ticket_response}")

    if ticket_response.get('ticket'):
        ticket = ticket_response['ticket']
        # Удаляем тикет
        try:
            post(f'http://127.0.0.1:8080/api/delete_ticket/{ticket["id"]}')
            print(f"Тикет {ticket['id']} успешно удален")
            await update.message.reply_text(
                "Тикет закрыт. Спасибо за обращение! Если у вас появятся новые вопросы, создайте новый тикет командой /send_request")
        except Exception as e:
            print(f"Ошибка при удалении тикета: {e}")
            await update.message.reply_text("Произошла ошибка при закрытии тикета")
    else:
        print("Активный тикет не найден")
        await update.message.reply_text("Всего доброго!")

    # Очищаем все данные
    context.user_data.clear()
    chat_id = ''
    data = []
    return ConversationHandler.END


async def send_support_message(update, context):
    """Обработчик команды /message"""
    message_text = ' '.join(context.args)
    chat_id = str(update.message.chat.id)
    message_id = update.message.message_id

    # Получаем тикет по chat_id
    ticket_response = get(
        f'http://127.0.0.1:8080/api/ticket_by_chat/{chat_id}').json()

    if not ticket_response.get('ticket'):
        await update.message.reply_text(
            "У вас нет активного тикета. Создайте новый тикет с помощью команды /send_request")
        return

    ticket = ticket_response['ticket']

    # Проверяем, не закрыт ли тикет
    if ticket.get('is_finished'):
        await update.message.reply_text(
            "Этот тикет уже закрыт. Если у вас появились новые вопросы, создайте новый тикет командой /send_request")
        context.user_data.clear()  # Очищаем данные пользователя
        return

    if not message_text:
        await update.message.reply_text(
            "Пожалуйста, добавьте текст сообщения после команды, например:\n"
            "/message Мой принтер перестал работать")
        return

    print(
        f"Получено сообщение через команду: ID={message_id}, chat_id={chat_id}, text={message_text}")

    # Сохраняем сообщение в JSON
    messages_dir = 'messages'
    if not os.path.exists(messages_dir):
        os.makedirs(messages_dir)

    filename = f'messages/{ticket["id"]}data.json'
    print(f"Сохраняем в файл: {filename}")

    message_data = {
        "message_id": message_id,
        "text": message_text,
        "sender_type": "client",
        "sender_name": ticket["name"],
        "timestamp": int(time.time())
    }

    try:
        if not os.path.exists(filename):
            data = {"messages": [message_data]}
        else:
            with open(filename, "r", encoding='utf-8') as json_file:
                data = json.load(json_file)
                if "messages" not in data:
                    data["messages"] = []
                # Проверяем, нет ли уже такого сообщения
                if not any(msg["message_id"] == message_id for msg in data["messages"]):
                    data["messages"].append(message_data)

        # Сохраняем обновленные данные
        with open(filename, "w", encoding='utf-8') as json_file:
            json.dump(data, json_file, indent=2, ensure_ascii=False)
            print(f"Сообщение успешно сохранено в {filename}")

    except Exception as e:
        print(f"Ошибка при сохранении сообщения: {e}")
        await update.message.reply_text("Произошла ошибка при сохранении сообщения")
        return

    # Обновляем last_id в тикете
    response = post('http://127.0.0.1:8080/api/update_last_id',
                    json={'ticket_id': ticket['id'], 'last_id': message_id})
    print(f"Ответ API update_last_id: {response.json()}")

    await update.message.reply_text("Ваше сообщение отправлено в техподдержку")


# def sender(message):
#    chat_id = 2118178098  # Сюда помещаем id пользователя кому будет отправлено сообщение
#    bot.send_message(chat_id, message)


def main() -> None:
    # Проверяем, не запущен ли уже бот
    check_running()

    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        application = Application.builder().token(
            "6874396479:AAETyIiiUhpR-pJlW7cwcX0Sd59yDI8jqVc").build()

        # Создаем обработчик команды stop отдельно
        stop_handler = CommandHandler('stop', stop)

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('send_request', start)],
            states={
                1: [MessageHandler(filters.TEXT & ~filters.COMMAND, first_response)],
                2: [MessageHandler(filters.TEXT & ~filters.COMMAND, second_response)],
                3: [MessageHandler(filters.TEXT & ~filters.COMMAND, third_response)],
                4: [MessageHandler(filters.TEXT & ~filters.COMMAND, fourth_response)],
                5: [MessageHandler(filters.TEXT & ~filters.COMMAND, fifth_response)],
                6: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat_message)],
            },
            fallbacks=[
                stop_handler,  # Добавляем обработчик stop
                CommandHandler('message', send_support_message),
                CommandHandler('send_request', start)
            ]
        )

        # Регистрируем обработчики
        application.add_handler(conv_handler)
        # Добавляем обработчик stop глобально
        application.add_handler(stop_handler)

        # Запускаем бота
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    finally:
        # Очищаем PID файл при выходе
        cleanup()


if __name__ == "__main__":
    main()
    # sender("lol")
