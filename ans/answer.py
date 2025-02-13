from flask import Flask, render_template, redirect, abort, flash, jsonify, request
from requests import get, post
from data import db_session, vocord_tickets_api
from forms.user import RegisterForm, LoginForm
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
    if name is None:
        return redirect('/login')

    try:
        db_sess = db_session.create_session()
        current_user = db_sess.query(User).filter(
            User.surname + ' ' + User.name == name).first()

        if not current_user:
            return redirect('/login')

        if admin:
            # Для админа показываем нераспределенные тикеты
            unassigned = get(
                'http://127.0.0.1:8080/api/get_unassigned_tickets').json()['tickets']
            unassigned_list = [[
                t['id'],
                t['problem_name'],
                t['name'],
                t['product_name'],
                t['created_at'],
            ] for t in unassigned]

            # Получаем список всех сотрудников поддержки
            support_users = db_sess.query(
                User).filter(User.admin == False).all()
        else:
            unassigned_list = []
            support_users = []

        # Получаем тикеты, назначенные текущему пользователю
        assigned = get(
            f'http://127.0.0.1:8080/api/get_user_tickets/{current_user.id}').json()['tickets']
        assigned_list = [[
            t['id'],
            t['problem_name'],
            t['name'],
            t['product_name'],
            t['created_at'],
            f"document.location='http://127.0.0.1:8080/ticket/{t['id']}'"
        ] for t in assigned]

        return render_template('desk.html',
                               title='Vocord technical support desk',
                               unassigned=unassigned_list,
                               news=assigned_list,
                               support_users=support_users,
                               name=name,
                               is_admin=admin,
                               current_user=current_user)
    except Exception as e:
        print(f"Ошибка при загрузке страницы desk: {e}")
        return render_template('desk.html',
                               title='Vocord technical support desk',
                               unassigned=[],
                               news=[],
                               support_users=[],
                               name=name,
                               is_admin=admin,
                               current_user=current_user)


@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


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

        # Получаем текущего пользователя
        current_user = db_sess.query(User).filter(
            User.surname + ' ' + User.name == name).first()

        # Проверяем права доступа к тикету (админ может смотреть любые тикеты)
        if not admin and ticket.assigned_to != current_user.id:
            flash('У вас нет прав на просмотр этого тикета')
            return redirect('/my_desk')

        # Загружаем сообщения из JSON файла
        filename = f'messages/{ticket_number}data.json'
        messages = []

        if os.path.exists(filename):
            with open(filename, encoding='utf-8') as json_file:
                data = json.load(json_file)
                messages = data.get("messages", [])

        # Получаем новые сообщения из Telegram только если тикет не закрыт
        if not ticket.is_finished:
            token = "6874396479:AAETyIiiUhpR-pJlW7cwcX0Sd59yDI8jqVc"
            updates = get(
                f'http://api.telegram.org/bot{token}/getUpdates?offset=0').json()

            if updates.get('ok'):
                messages_updated = False
                for update in updates['result']:
                    if ('message' in update and
                            str(update['message']['chat']['id']) == ticket.chat_id):

                        message_id = update['message']['message_id']
                        message_text = update['message'].get('text', '')

                        # Пропускаем команды
                        if message_text.startswith('/'):
                            continue

                        # Проверяем, не добавлено ли уже это сообщение
                        if not any(msg["message_id"] == message_id for msg in messages):
                            message_data = {
                                "message_id": message_id,
                                "text": message_text,
                                "sender_type": "client",
                                "sender_name": ticket.name,
                                "timestamp": update['message']['date']
                            }
                            messages.append(message_data)
                            messages_updated = True

                if messages_updated:
                    # Сортируем сообщения по времени
                    messages.sort(key=lambda x: x["timestamp"])
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump({"messages": messages}, f,
                                  indent=2, ensure_ascii=False)

        return render_template('new_ticket.html',
                               title=f'Тикет №{ticket_number}',
                               ticket=ticket,
                               messages=messages,
                               name=name,
                               is_admin=admin,
                               current_user=current_user)


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


@app.route('/api/close_ticket', methods=['POST'])
def close_ticket_api():
    """Закрыть тикет через API"""
    if not request.json or 'ticket_id' not in request.json:
        return jsonify({'error': 'Missing ticket_id'}), 400

    try:
        db_sess = db_session.create_session()
        ticket = db_sess.query(Ticket).get(request.json['ticket_id'])

        if not ticket:
            return jsonify({'error': 'Ticket not found'}), 404

        if ticket.is_finished:
            return jsonify({'error': 'Ticket already closed'}), 400

        # Закрываем тикет
        ticket.is_finished = True
        db_sess.commit()

        return jsonify({
            'success': True,
            'chat_id': ticket.chat_id  # Возвращаем chat_id для очистки данных в боте
        })
    except Exception as e:
        print(f"Ошибка при закрытии тикета: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete_ticket/<int:ticket_id>', methods=['POST'])
def delete_ticket(ticket_id):
    db_sess = db_session.create_session()
    ticket = db_sess.query(Ticket).get(ticket_id)

    if not ticket:
        return jsonify({'error': 'Not found'})

    # Отправляем сообщение пользователю в Telegram
    chat_id = ticket.chat_id
    token = "6874396479:AAETyIiiUhpR-pJlW7cwcX0Sd59yDI8jqVc"
    message = "Тикет закрыт. Спасибо за обращение! Если у вас появятся новые вопросы, создайте новый тикет командой /send_request"

    post(
        f'http://api.telegram.org/bot{token}/sendmessage?chat_id={chat_id}&text={message}')

    # Удаляем файл с сообщениями
    messages_file = f'messages/{ticket_id}data.json'
    if os.path.exists(messages_file):
        os.remove(messages_file)

    # Удаляем тикет из БД
    db_sess.delete(ticket)
    db_sess.commit()

    return jsonify({'success': 'OK'})


@app.route('/api/assign_ticket', methods=['POST'])
def assign_ticket():
    """Назначить тикет сотруднику"""
    if not request.json:
        return jsonify({'error': 'Empty request'})

    db_sess = db_session.create_session()
    ticket = db_sess.query(Ticket).get(request.json['ticket_id'])
    user = db_sess.query(User).get(request.json['user_id'])

    if not ticket or not user:
        return jsonify({'error': 'Not found'})

    ticket.assigned_to = user.id
    ticket.worker = f"{user.surname} {user.name}"
    db_sess.commit()

    return jsonify({'success': 'OK'})


@app.route('/api/get_unassigned_tickets')
def get_unassigned_tickets():
    """Получить все нераспределенные тикеты"""
    try:
        db_sess = db_session.create_session()
        tickets = db_sess.query(Ticket).filter(
            Ticket.assigned_to == None,
            Ticket.is_finished == False  # Добавляем фильтр по незакрытым тикетам
        ).all()
        return jsonify({
            'tickets': [item.to_dict(
                only=('id', 'problem_name', 'name',
                      'product_name', 'created_at')
            ) for item in tickets]
        })
    except Exception as e:
        print(f"Ошибка при получении нераспределенных тикетов: {e}")
        return jsonify({'tickets': []})


@app.route('/api/get_user_tickets/<int:user_id>')
def get_user_tickets(user_id):
    """Получить все тикеты, назначенные пользователю"""
    try:
        db_sess = db_session.create_session()
        tickets = db_sess.query(Ticket).filter(
            Ticket.assigned_to == user_id,
            Ticket.is_finished == False  # Добавляем фильтр по незакрытым тикетам
        ).all()
        return jsonify({
            'tickets': [item.to_dict(
                only=('id', 'problem_name', 'name',
                      'product_name', 'created_at')
            ) for item in tickets]
        })
    except Exception as e:
        print(f"Ошибка при получении тикетов пользователя: {e}")
        return jsonify({'tickets': []})


@app.route('/api/ticket_by_chat/<chat_id>')
def get_ticket_by_chat(chat_id):
    print(f"Получен запрос для chat_id: {chat_id}")
    try:
        db_sess = db_session.create_session()
        ticket = db_sess.query(Ticket).filter(
            Ticket.chat_id == chat_id).first()
        print(f"Найден тикет: {ticket}")
        return jsonify({'ticket': ticket.to_dict() if ticket else None})
    except Exception as e:
        print(f"Ошибка при поиске тикета: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/test')
def test_api():
    return jsonify({'status': 'ok'})


@app.route('/assign_worker/<int:ticket_id>', methods=['POST'])
def assign_worker(ticket_id):
    """Назначить сотрудника на тикет"""
    if not request.form.get('worker_id'):
        flash('Выберите сотрудника')
        return redirect('/my_desk')

    try:
        db_sess = db_session.create_session()
        ticket = db_sess.query(Ticket).get(ticket_id)
        worker = db_sess.query(User).get(request.form.get('worker_id'))

        if not ticket or not worker:
            flash('Тикет или сотрудник не найден')
            return redirect('/my_desk')

        ticket.assigned_to = worker.id
        ticket.worker = f"{worker.surname} {worker.name}"
        db_sess.commit()

        flash(
            f'Тикет №{ticket_id} назначен сотруднику {worker.surname} {worker.name}')
    except Exception as e:
        print(f"Ошибка при назначении сотрудника: {e}")
        flash('Произошла ошибка при назначении сотрудника')

    return redirect('/my_desk')


@app.route('/profile')
def profile():
    """Страница профиля текущего пользователя"""
    global name, admin
    if name is None:
        return redirect('/login')

    try:
        db_sess = db_session.create_session()
        current_user = db_sess.query(User).filter(
            User.surname + ' ' + User.name == name).first()

        if not current_user:
            return redirect('/login')

        # Получаем статистику по тикетам
        active_tickets = db_sess.query(Ticket).filter(
            Ticket.assigned_to == current_user.id,
            Ticket.is_finished == False
        ).count()

        closed_tickets = db_sess.query(Ticket).filter(
            Ticket.assigned_to == current_user.id,
            Ticket.is_finished == True
        ).count()

        return render_template('profile.html',
                               title='Профиль',
                               name=name,
                               user=current_user,
                               active_tickets=active_tickets,
                               closed_tickets=closed_tickets)

    except Exception as e:
        print(f"Ошибка при загрузке профиля: {e}")
        flash('Произошла ошибка при загрузке профиля')
        return redirect('/my_desk')


@app.route('/')
def index():
    """Главная страница"""
    global name, admin

    if name is None:
        return render_template('index.html',
                               title='Главная',
                               name=None)

    try:
        db_sess = db_session.create_session()
        current_user = db_sess.query(User).filter(
            User.surname + ' ' + User.name == name).first()

        if not current_user:
            return redirect('/login')

        # Получаем статистику по тикетам
        active_tickets = db_sess.query(Ticket).filter(
            Ticket.assigned_to == current_user.id,
            Ticket.is_finished == False
        ).count()

        closed_tickets = db_sess.query(Ticket).filter(
            Ticket.assigned_to == current_user.id,
            Ticket.is_finished == True
        ).count()

        return render_template('index.html',
                               title='Главная',
                               name=name,
                               is_admin=admin,
                               active_tickets=active_tickets,
                               closed_tickets=closed_tickets)

    except Exception as e:
        print(f"Ошибка при загрузке главной страницы: {e}")
        flash('Произошла ошибка при загрузке страницы')
        return render_template('index.html',
                               title='Главная',
                               name=name,
                               is_admin=admin)


@app.route('/staff')
def staff_list():
    """Страница со списком сотрудников"""
    global name, admin
    if not admin:
        return redirect('/')

    try:
        db_sess = db_session.create_session()
        users = db_sess.query(User).all()

        # Добавляем количество активных тикетов для каждого пользователя
        for user in users:
            user.active_tickets = db_sess.query(Ticket).filter(
                Ticket.assigned_to == user.id,
                Ticket.is_finished == False
            ).count()

        return render_template('staff_list.html',
                               title='Сотрудники',
                               name=name,
                               is_admin=admin,
                               users=users)
    except Exception as e:
        print(f"Ошибка при загрузке списка сотрудников: {e}")
        flash('Произошла ошибка при загрузке списка сотрудников')
        return redirect('/')


@app.route('/staff/<int:user_id>')
def view_staff_member(user_id):
    """Страница просмотра сотрудника"""
    global name, admin
    if not admin:
        return redirect('/')

    try:
        db_sess = db_session.create_session()
        user = db_sess.query(User).get(user_id)

        if not user:
            flash('Сотрудник не найден')
            return redirect('/staff')

        # Получаем статистику
        active_tickets = db_sess.query(Ticket).filter(
            Ticket.assigned_to == user.id,
            Ticket.is_finished == False
        ).count()

        # Получаем все закрытые тикеты
        closed_tickets_query = db_sess.query(Ticket).filter(
            Ticket.assigned_to == user.id,
            Ticket.is_finished == True
        )

        closed_tickets = closed_tickets_query.count()
        closed_tickets_list = closed_tickets_query.order_by(
            Ticket.created_at.desc()).all()

        return render_template('staff_member.html',
                               title=f'Сотрудник: {user.surname} {user.name}',
                               name=name,
                               is_admin=admin,
                               user=user,
                               active_tickets=active_tickets,
                               closed_tickets=closed_tickets,
                               closed_tickets_list=closed_tickets_list)
    except Exception as e:
        print(f"Ошибка при просмотре сотрудника: {e}")
        flash('Произошла ошибка при загрузке данных сотрудника')
        return redirect('/staff')


@app.route('/close_ticket/<int:ticket_id>', methods=['POST'])
def close_ticket(ticket_id):
    """Закрыть тикет через веб-интерфейс"""
    global name, admin
    if name is None:
        return redirect('/login')

    try:
        db_sess = db_session.create_session()
        ticket = db_sess.query(Ticket).get(ticket_id)
        current_user = db_sess.query(User).filter(
            User.surname + ' ' + User.name == name).first()

        if not ticket:
            flash('Тикет не найден')
            return redirect('/my_desk')

        # Проверяем права на закрытие тикета
        if not admin and ticket.assigned_to != current_user.id:
            flash('У вас нет прав на закрытие этого тикета')
            return redirect(f'/ticket/{ticket_id}')

        if ticket.is_finished:
            flash('Тикет уже закрыт')
            return redirect(f'/ticket/{ticket_id}')

        # Закрываем тикет
        ticket.is_finished = True
        db_sess.commit()

        # Отправляем уведомление в Telegram
        chat_id = ticket.chat_id
        token = "6874396479:AAETyIiiUhpR-pJlW7cwcX0Sd59yDI8jqVc"
        message = "Тикет был закрыт сотрудником техподдержки. Если у вас появятся новые вопросы, создайте новый тикет командой /send_request"

        post(
            f'http://api.telegram.org/bot{token}/sendmessage?chat_id={chat_id}&text={message}')

        flash('Тикет успешно закрыт')
        return redirect('/my_desk')

    except Exception as e:
        print(f"Ошибка при закрытии тикета: {e}")
        flash('Произошла ошибка при закрытии тикета')
        return redirect(f'/ticket/{ticket_id}')


@app.route('/api/all_tickets_by_chat/<chat_id>')
def get_all_tickets_by_chat(chat_id):
    """Получить все тикеты по chat_id"""
    try:
        db_sess = db_session.create_session()
        tickets = db_sess.query(Ticket).filter(
            Ticket.chat_id == chat_id
        ).order_by(Ticket.created_at.desc()).all()

        return jsonify({
            'tickets': [ticket.to_dict() for ticket in tickets]
        })
    except Exception as e:
        print(f"Ошибка при получении тикетов: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/take_ticket', methods=['POST'])
def take_ticket():
    """Админ берет тикет себе"""
    global name, admin
    if not admin:
        return jsonify({'error': 'Недостаточно прав'}), 403

    if not request.json or 'ticket_id' not in request.json:
        return jsonify({'error': 'Missing ticket_id'}), 400

    try:
        db_sess = db_session.create_session()
        ticket = db_sess.query(Ticket).get(request.json['ticket_id'])
        current_user = db_sess.query(User).filter(
            User.surname + ' ' + User.name == name).first()

        if not ticket:
            return jsonify({'error': 'Тикет не найден'}), 404

        if ticket.is_finished:
            return jsonify({'error': 'Тикет уже закрыт'}), 400

        if ticket.assigned_to:
            return jsonify({'error': 'Тикет уже назначен'}), 400

        # Назначаем тикет админу
        ticket.assigned_to = current_user.id
        ticket.worker = f"{current_user.surname} {current_user.name}"
        db_sess.commit()

        # Отправляем уведомление в Telegram
        chat_id = ticket.chat_id
        token = "6874396479:AAETyIiiUhpR-pJlW7cwcX0Sd59yDI8jqVc"
        message = f"Ваш тикет взят в работу специалистом {current_user.surname} {current_user.name}"

        post(
            f'http://api.telegram.org/bot{token}/sendmessage?chat_id={chat_id}&text={message}')

        return jsonify({'success': True})

    except Exception as e:
        print(f"Ошибка при назначении тикета: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/send_message/<int:ticket_id>', methods=['POST'])
def api_send_message(ticket_id):
    """API endpoint для отправки сообщений"""
    global name, admin
    if name is None:
        return jsonify({'error': 'Необходима авторизация'}), 401

    if not request.json or 'text' not in request.json:
        return jsonify({'error': 'Отсутствует текст сообщения'}), 400

    try:
        db_sess = db_session.create_session()
        ticket = db_sess.query(Ticket).get(ticket_id)
        current_user = db_sess.query(User).filter(
            User.surname + ' ' + User.name == name).first()

        if not ticket:
            return jsonify({'error': 'Тикет не найден'}), 404

        if ticket.is_finished:
            return jsonify({'error': 'Тикет закрыт'}), 400

        if not admin and ticket.assigned_to != current_user.id:
            return jsonify({'error': 'Нет прав на ответ в этом тикете'}), 403

        # Отправляем сообщение в Telegram
        chat_id = ticket.chat_id
        token = "6874396479:AAETyIiiUhpR-pJlW7cwcX0Sd59yDI8jqVc"
        text = request.json['text']

        response = post(
            f'http://api.telegram.org/bot{token}/sendmessage?chat_id={chat_id}&text={text}')

        if response.status_code == 200:
            message_id = response.json()['result']['message_id']

            # Сохраняем сообщение в JSON
            filename = f'messages/{ticket_id}data.json'

            if not os.path.exists('messages'):
                os.makedirs('messages')

            message_data = {
                "message_id": message_id,
                "text": text,
                "sender_type": "support",
                "sender_name": f"{current_user.surname} {current_user.name}",
                "timestamp": int(time.time())
            }

            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {"messages": []}

            data["messages"].append(message_data)

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Ошибка отправки сообщения в Telegram'}), 500

    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.register_blueprint(vocord_tickets_api.blueprint)
    app.run(port=8080, host='127.0.0.1', debug=True)
