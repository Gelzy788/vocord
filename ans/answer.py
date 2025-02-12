from flask import Flask, render_template, redirect, abort
from requests import get, post
from data import db_session, vocord_tickets_api
from forms.user import RegisterForm, LoginForm, SendForm
from data.users import User
# from forms.ticket import TicketForm
from data.tickets import Ticket
from flask_login import LoginManager, login_required
from flask_login import login_user, logout_user
import os
import json
from contextlib import contextmanager
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key'
db_session.global_init("db/vocord.sqlite")
login_manager = LoginManager()
login_manager.init_app(app)
name = None
admin = False


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = db_session.create_session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


@login_manager.user_loader
def load_user(user_id):
    with session_scope() as db_sess:
        return db_sess.query(User).get(user_id)


@app.route('/logout')
@login_required
def logout():
    global name, admin
    logout_user()
    name, admin = None, False
    return redirect("/")


@app.route('/my_desk')
def desk():
    global name, admin
    news = []
    in_works = []
    for el in get('http://127.0.0.1:8080/api/all_tickets/0').json()['tickets']:
        news.append([el['id'], el['problem_name'], el['name'], el['product_name'], el['created_at'],
                    "document.location='http://127.0.0.1:8080/ticket/" + str(el['id']) + "'"])
    if name is None:
        return redirect('/login')
    return render_template('desk.html', title='Vocord technical support desk', news=news, in_works=in_works)


@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.route('/send_message/<int:ticket_number>', methods=['GET', 'POST'])
def send_message(ticket_number):
    form = SendForm()
    if form.validate_on_submit():
        text = form.text.data
        with session_scope() as db_sess:
            ticket = db_sess.query(Ticket).filter(
                Ticket.id == ticket_number).first()
            if not ticket:
                abort(404)

            chat_id = ticket.chat_id
            token = "6874396479:AAETyIiiUhpR-pJlW7cwcX0Sd59yDI8jqVc"

            # Отправляем сообщение в Telegram
            response = post(
                f'http://api.telegram.org/bot{token}/sendmessage?chat_id={chat_id}&text={text}')

            if response.status_code == 200:
                message_id = response.json()['result']['message_id']

                # Сохраняем сообщение в JSON
                messages_dir = 'messages'
                if not os.path.exists(messages_dir):
                    os.makedirs(messages_dir)

                filename = f'messages/{ticket_number}data.json'

                message_data = {
                    "message_id": message_id,
                    "text": text,
                    "sender_type": "support",
                    "sender_name": name,  # Имя сотрудника поддержки
                    "timestamp": int(time.time())
                }

                if not os.path.exists(filename):
                    data = {"messages": [message_data]}
                else:
                    with open(filename, "r") as json_file:
                        data = json.load(json_file)
                        data["messages"].append(message_data)

                with open(filename, 'w') as f:
                    json.dump(data, f, indent=2)

                return redirect(f'/ticket/{ticket_number}')

    return render_template('letter.html', title='Ответ на обращение', form=form, name=name)


@app.route('/ticket/<int:ticket_number>')
def beloved_ticket(ticket_number):
    global name, admin
    if name is None:
        return redirect('/login')

    with session_scope() as db_sess:
        ticket = db_sess.query(Ticket).filter(
            Ticket.id == ticket_number).first()
        if not ticket:
            abort(404)

        print(f"Загружаем тикет: {ticket.to_dict()}")  # Отладка

        token = "6874396479:AAETyIiiUhpR-pJlW7cwcX0Sd59yDI8jqVc"

        # Загружаем сообщения из JSON файла
        filename = f'messages/{ticket_number}data.json'
        messages = []

        if os.path.exists(filename):
            with open(filename) as json_file:
                data = json.load(json_file)
                messages = data.get("messages", [])
                print(f"Загруженные сообщения из файла: {messages}")

        # Получаем новые сообщения из Telegram
        updates = get(
            f'http://api.telegram.org/bot{token}/getUpdates?offset=0').json()

        print(f"Ответ Telegram API: {updates}")  # Отладка

        if updates.get('ok'):
            messages_updated = False
            for update in updates['result']:
                if ('message' in update and
                        str(update['message']['chat']['id']) == ticket.chat_id):

                    message_id = update['message']['message_id']
                    message_text = update['message'].get('text', '')

                    print(
                        f"Обрабатываем сообщение: ID={message_id}, text={message_text}")

                    # Пропускаем команды
                    if message_text.startswith('/'):
                        continue

                    # Проверяем, не добавлено ли уже это сообщение
                    if not any(msg["message_id"] == message_id for msg in messages):
                        print("Добавляем новое сообщение в список")

                        message_data = {
                            "message_id": message_id,
                            "text": message_text,
                            "sender_type": "client",
                            "sender_name": ticket.name,  # Имя клиента из тикета
                            "timestamp": update['message']['date']
                        }

                        messages.append(message_data)
                        messages_updated = True

            if messages_updated:
                # Сортируем сообщения по времени
                messages.sort(key=lambda x: x["timestamp"])

                print(f"Сохраняем обновленные сообщения: {messages}")
                with open(filename, 'w') as f:
                    json.dump({"messages": messages}, f, indent=2)

        return render_template('new_ticket.html',
                               title=ticket.problem_name,
                               ticket=ticket.to_dict(),
                               name=name,
                               messages=messages)


@app.route('/add_new_user', methods=['GET', 'POST'])
def register():
    global name, admin
    if name is None:
        redirect('/login')
    if not admin:
        abort(404)
    form = RegisterForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        user = User(name=form.name.data,
                    email=form.email.data,
                    surname=form.surname.data,
                    last_name=form.last_name.data,
                    login=form.login.data,
                    admin=form.admin.data)
        user.set_password(form.password.data)
        db_sess.add(user)
        db_sess.commit()
        return redirect("/my_desk")
    return render_template('register.html', title='Регистрация', form=form, name=name)


@app.route('/login', methods=['GET', 'POST'])
def login():
    global name, admin
    form = LoginForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        user = db_sess.query(User).filter(
            User.login == form.login.data).first()
        print(user)
        print(form.password.data)
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            name = user.surname + ' ' + user.name
            admin = user.admin
            print(name, admin)
            return redirect("/my_desk")
        return render_template('login.html',
                               message="Неправильный логин или пароль",
                               form=form, name=name)
    return render_template('login.html', title='Авторизация', form=form, name=name)


@app.template_filter('datetime')
def format_datetime(timestamp):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))


@app.after_request
def add_header(response):
    # Отключаем кэширование
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    # Убираем заголовок Refresh
    if 'Refresh' in response.headers:
        del response.headers['Refresh']
    return response


if __name__ == '__main__':
    app.register_blueprint(vocord_tickets_api.blueprint)
    app.run(port=8080, host='127.0.0.1')
