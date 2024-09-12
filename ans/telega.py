import logging
from telegram import Update, ReplyKeyboardMarkup
from requests import post
import re
import datetime
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters

# set global variables
data = []
chat_id = ''

# configure logging module to output debug information to console
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

# reply_keyboard = [['Да', 'Нет']]
product_list = [['VOCORD MicroCyclops', 'VOCORD Cyclops', 'VOCORD Cyclops Portable'],
                ['VOCORD SSCross', 'VOCORD SMCross', 'VOCORD NCCross'],
                ['VOCORD VERelay 6', 'VOCORD TLCross'],
                ['Комплекс освещения VOCORD'],
                ['VOCORD Tahion', 'VOCORD ParkingControl']]
# markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
product_markup = ReplyKeyboardMarkup(product_list, one_time_keyboard=True)


def check_email(email):
    # Для проверки корректности пароля
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    return re.match(pattern, email)


async def start(update, context):
    await update.message.reply_text(
        "Здравствуйте! Я - бот техподдержки Вокорда! "
        "Вы можете прислать нам описание Вашей проблемы и мы в скором времени свяжемся с Вами! "
        "Если Вы передумали или Ваша проблема была устранена нажмите /stop. "
        "Для связи с Вами нам нужно знать как к Вам обращаться! "
        "Пожалуйста, напишите Ваше ФИО с пробелами.")
    return 1


async def first_response(update, context):
    global data, chat_id
    chat_id = str(update.message.chat.id)
    data.append(update.message.text)
    logger.info(data[-1])
    await update.message.reply_text(
        f"Для связи, мы используем почту.\n"
        f"(Пришлите Ваш адрес почты, в котором должен присутствовать символ '@')")
    return 2


async def second_response(update, context):
    global data
    data.append(update.message.text)
    logger.info(data[-1])
    if not check_email(email=data[-1]):
        await update.message.reply_text("Некорректная почта!")
        del data[-1]
        return 2
    await update.message.reply_text("Пришлите название нашего продукта или выберите из списка,"
                                    " проблему о котором вы хотите задать!",
                                    reply_markup=product_markup)
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
    await update.message.reply_text("Спасибо за отзыв!"
                                    "\nМы постараемся решить вашу проблему как можно быстрее."
                                    "\nВсего доброго!")
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
    chat_id = ''
    return ConversationHandler.END


async def stop(update, context):
    global data, chat_id
    chat_id = ''
    data = []
    await update.message.reply_text("Всего доброго!")
    return ConversationHandler.END


def main() -> None:
    application = Application.builder().token("6874396479:AAETyIiiUhpR-pJlW7cwcX0Sd59yDI8jqVc").build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('send_request', start)],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, first_response)],
            2: [MessageHandler(filters.TEXT & ~filters.COMMAND, second_response)],
            3: [MessageHandler(filters.TEXT & ~filters.COMMAND, third_response)],
            4: [MessageHandler(filters.TEXT & ~filters.COMMAND, fourth_response)],
            5: [MessageHandler(filters.TEXT & ~filters.COMMAND, fifth_response)],
        },
        fallbacks=[CommandHandler(['stop'], stop)]
    )
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("send_request", start))
    application.add_handler(CommandHandler("stop", stop))
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
