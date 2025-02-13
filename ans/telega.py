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
import psutil

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

# Определяем базовый URL для API
API_BASE_URL = 'http://127.0.0.1:8080'  # Оставляем localhost


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
        try:
            with open(PID_FILE, 'r') as f:
                old_pid = int(f.read())

            # Для Windows используем специальную проверку
            if psutil.pid_exists(old_pid):
                print(f"Бот уже запущен (PID: {old_pid})")
                sys.exit(1)
            else:
                # Процесс не существует, удаляем старый PID файл
                os.remove(PID_FILE)
        except (ValueError, OSError):
            # Если файл поврежден или не читается, удаляем его
            os.remove(PID_FILE)

    # Записываем текущий PID
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))


def check_server():
    """Проверяет доступность сервера"""
    try:
        response = get(f'{API_BASE_URL}/api/test')
        if response.status_code == 200:
            print("Сервер успешно запущен и доступен")
            return True
        print(f"Сервер недоступен, код ответа: {response.status_code}")
        return False
    except Exception as e:
        print(f"Ошибка при проверке сервера: {e}")
        return False


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
    current_chat_id = str(update.message.chat.id)

    try:
        # Проверяем все тикеты пользователя
        response = get(
            f'{API_BASE_URL}/api/all_tickets_by_chat/{current_chat_id}')

        if response.status_code != 200:
            print(f"Ошибка сервера: {response.status_code}")
            print(f"Ответ сервера: {response.text}")
            await update.message.reply_text(
                "Извините, сервер временно недоступен. Попробуйте позже.")
            return ConversationHandler.END

        tickets = response.json().get('tickets', [])

        # Проверяем, есть ли активный тикет
        active_ticket = next(
            (ticket for ticket in tickets if not ticket.get('is_finished')), None)

        if active_ticket:
            await update.message.reply_text(
                "У вас уже есть активный тикет. Пожалуйста, дождитесь ответа специалиста или закройте текущий тикет командой /stop")
            # Возвращаем состояние чата вместо END
            return 6

    except Exception as e:
        print(f"Ошибка при проверке тикета: {e}")
        await update.message.reply_text(
            "Извините, произошла ошибка. Убедитесь, что сервер запущен и попробуйте снова.")
        return ConversationHandler.END

    # Очищаем предыдущие данные и сбрасываем состояние
    context.user_data.clear()
    global data, chat_id
    data = []
    chat_id = current_chat_id  # Устанавливаем новый chat_id

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

    # Получаем тикет по chat_id
    ticket_response = get(
        f'{API_BASE_URL}/api/ticket_by_chat/{chat_id}').json()

    # Проверяем, есть ли активный тикет
    if ticket_response.get('ticket') and not ticket_response['ticket'].get('is_finished'):
        await update.message.reply_text(
            "У вас уже есть активный тикет. Пожалуйста, дождитесь ответа специалиста или закройте текущий тикет командой /stop")
        context.user_data.clear()
        return ConversationHandler.END

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

    # Проверяем, есть ли активный тикет
    ticket_response = get(
        f'{API_BASE_URL}/api/ticket_by_chat/{current_chat_id}').json()

    if ticket_response.get('ticket') and not ticket_response['ticket'].get('is_finished'):
        await update.message.reply_text(
            "У вас уже есть активный тикет. Пожалуйста, дождитесь ответа специалиста или закройте текущий тикет командой /stop")
        context.user_data.clear()
        return ConversationHandler.END

    await update.message.reply_text(
        "Спасибо за отзыв!\n"
        "Мы постараемся решить вашу проблему как можно быстрее.\n"
        "Теперь вы можете отправлять сообщения прямо в чат или использовать команду /message, например:\n"
        "/message У меня появился еще один вопрос")

    # Создаем новый тикет
    response = post(f'{API_BASE_URL}/api/add_ticket',
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


async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений в чате"""
    chat_id = str(update.message.chat_id)

    # Получаем текущий тикет
    response = get(f'http://127.0.0.1:8080/api/ticket_by_chat/{chat_id}')
    if response.status_code != 200:
        await update.message.reply_text(
            "Произошла ошибка. Пожалуйста, создайте новый тикет командой /send_request")
        context.user_data.clear()  # Очищаем данные при ошибке
        return ConversationHandler.END

    ticket_data = response.json().get('ticket')

    # Если тикет не найден
    if not ticket_data:
        await update.message.reply_text(
            "Для отправки сообщения создайте новый тикет командой /send_request")
        context.user_data.clear()
        return ConversationHandler.END

    # Проверяем, есть ли активный тикет для этого chat_id
    if ticket_data.get('is_finished'):
        # Проверяем, есть ли новый активный тикет
        all_tickets_response = get(
            f'http://127.0.0.1:8080/api/all_tickets_by_chat/{chat_id}')
        if all_tickets_response.status_code == 200:
            tickets = all_tickets_response.json().get('tickets', [])
            active_ticket = next(
                (t for t in tickets if not t.get('is_finished')), None)

            if active_ticket:
                ticket_data = active_ticket
            else:
                await update.message.reply_text(
                    "Этот тикет закрыт. Для отправки нового сообщения создайте новый тикет командой /send_request")
                context.user_data.clear()
                return ConversationHandler.END

    # Сохраняем сообщение
    message_data = {
        "message_id": update.message.message_id,
        "text": update.message.text,
        "sender_type": "client",
        "sender_name": ticket_data['name'],
        "timestamp": int(time.time())
    }

    # Сохраняем сообщение в JSON
    filename = f'messages/{ticket_data["id"]}data.json'

    if not os.path.exists('messages'):
        os.makedirs('messages')

    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {"messages": []}

    data["messages"].append(message_data)

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return 6


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Закрыть тикет"""
    chat_id = str(update.message.chat_id)

    # Получаем тикет по chat_id
    response = get(f'http://127.0.0.1:8080/api/ticket_by_chat/{chat_id}')
    if response.status_code != 200:
        await update.message.reply_text("Произошла ошибка при поиске тикета")
        return ConversationHandler.END

    ticket_data = response.json().get('ticket')
    if not ticket_data:
        await update.message.reply_text("Активный тикет не найден")
        return ConversationHandler.END

    # Проверяем, не закрыт ли уже тикет
    if ticket_data.get('is_finished'):
        await update.message.reply_text("Этот тикет уже закрыт")
        return ConversationHandler.END

    # Закрываем тикет через API
    response = post('http://127.0.0.1:8080/api/close_ticket',
                    json={'ticket_id': ticket_data['id']})

    if response.status_code == 200:
        # Очищаем данные пользователя
        context.user_data.clear()

        await update.message.reply_text(
            "Тикет закрыт. Если у вас появятся новые вопросы, "
            "создайте новый тикет командой /send_request")
    else:
        await update.message.reply_text("Произошла ошибка при закрытии тикета")

    return ConversationHandler.END


async def send_support_message(update, context):
    """Обработчик команды /message"""
    message_text = ' '.join(context.args)
    chat_id = str(update.message.chat.id)
    message_id = update.message.message_id

    # Получаем тикет по chat_id
    ticket_response = get(
        f'{API_BASE_URL}/api/ticket_by_chat/{chat_id}').json()

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
    response = post(f'{API_BASE_URL}/api/update_last_id',
                    json={'ticket_id': ticket['id'], 'last_id': message_id})
    print(f"Ответ API update_last_id: {response.json()}")

    await update.message.reply_text("Ваше сообщение отправлено в техподдержку")


# def sender(message):
#    chat_id = 2118178098  # Сюда помещаем id пользователя кому будет отправлено сообщение
#    bot.send_message(chat_id, message)


def main() -> None:
    # Проверяем, не запущен ли уже бот
    check_running()

    # Проверяем доступность сервера
    if not check_server():
        print("ОШИБКА: Сервер недоступен. Пожалуйста, запустите сначала answer.py")
        sys.exit(1)

    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        application = Application.builder().token(
            "6874396479:AAETyIiiUhpR-pJlW7cwcX0Sd59yDI8jqVc").build()

        # Создаем фильтр для всех команд
        command_filter = filters.COMMAND

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('send_request', start)],
            states={
                1: [MessageHandler(filters.TEXT & ~command_filter, first_response)],
                2: [MessageHandler(filters.TEXT & ~command_filter, second_response)],
                3: [MessageHandler(filters.TEXT & ~command_filter, third_response)],
                4: [MessageHandler(filters.TEXT & ~command_filter, fourth_response)],
                5: [MessageHandler(filters.TEXT & ~command_filter, fifth_response)],
                6: [MessageHandler(filters.TEXT & ~command_filter, handle_chat_message)],
            },
            fallbacks=[
                CommandHandler('stop', stop),
                CommandHandler('message', send_support_message),
                CommandHandler('send_request', start)
            ],
            allow_reentry=True
        )

        # Регистрируем только ConversationHandler
        application.add_handler(conv_handler)

        # Запускаем бота
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    finally:
        cleanup()


if __name__ == "__main__":
    main()
    # sender("lol")
