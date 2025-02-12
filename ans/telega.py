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
data = []
chat_id = ''
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.ERROR
)

logger = logging.getLogger(__name__)
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
    await update.message.reply_text(
        "Спасибо за отзыв!\n"
        "Мы постараемся решить вашу проблему как можно быстрее.\n"
        "Чтобы отправить дополнительное сообщение, используйте команду /message, например:\n"
        "/message У меня появился еще один вопрос")
    post('http://127.0.0.1:8080/api/add_ticket',
         json={'name': data[0],
               'email': data[1],
               'product_name': data[2],
               'problem_name': data[3],
               'problem_full': data[4],
               'is_finished': False,
               'worker': 'Не назначен',
               'chat_id': chat_id,
               'last_id': update.message.id
               }
         )
    data = []
    return 6  # Переходим в состояние чата


async def handle_chat_message(update, context):
    """Обработчик сообщений в режиме чата"""
    message_text = update.message.text
    chat_id = str(update.message.chat.id)
    message_id = update.message.message_id

    print(
        f"Получено сообщение в чате: ID={message_id}, chat_id={chat_id}, text={message_text}")

    # Получаем тикет по chat_id
    ticket_response = get(
        f'http://127.0.0.1:8080/api/ticket_by_chat/{chat_id}').json()
    print(f"Ответ API ticket_by_chat: {ticket_response}")

    if not ticket_response.get('ticket'):
        print(f"Тикет не найден для chat_id={chat_id}")
        return ConversationHandler.END

    ticket = ticket_response['ticket']
    print(f"Найден тикет: {ticket}")

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
    return 6


async def stop(update, context):
    global data, chat_id
    chat_id = ''
    data = []
    await update.message.reply_text("Всего доброго!")
    return ConversationHandler.END


async def send_support_message(update, context):
    """Обработчик команды /message"""
    message_text = ' '.join(context.args)  # Получаем текст после команды
    chat_id = str(update.message.chat.id)
    message_id = update.message.message_id

    if not message_text:
        await update.message.reply_text(
            "Пожалуйста, добавьте текст сообщения после команды, например:\n"
            "/message Мой принтер перестал работать")
        return

    print(
        f"Получено сообщение через команду: ID={message_id}, chat_id={chat_id}, text={message_text}")

    # Получаем тикет по chat_id
    ticket_response = get(
        f'http://127.0.0.1:8080/api/ticket_by_chat/{chat_id}').json()
    print(f"Ответ API ticket_by_chat: {ticket_response}")

    if not ticket_response.get('ticket'):
        await update.message.reply_text("Сначала создайте тикет с помощью команды /send_request")
        return

    ticket = ticket_response['ticket']

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
    application = Application.builder().token(
        "6874396479:AAETyIiiUhpR-pJlW7cwcX0Sd59yDI8jqVc").build()

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
            CommandHandler(['stop'], stop),
            # Добавляем команду message в fallbacks
            CommandHandler('message', send_support_message)
        ]
    )

    # Регистрируем обработчики в правильном порядке
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("send_request", start))
    application.add_handler(CommandHandler("stop", stop))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
    # sender("lol")
