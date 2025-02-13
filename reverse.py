from flask import Flask
from data import db_session
from data.users import User

app = Flask(__name__)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key'


def main():
    db_session.global_init("db/vocord.sqlite")
    db_sess = db_session.create_session()
    user = User()
    user.name = "Тимофей"
    user.email = "timofey.perunov@gmail.com"
    user.surname = "Перунов"
    user.last_name = "Николаевич"
    user.login = "tim"
    user.set_password("1234")
    user.admin = True
    db_sess = db_session.create_session()
    db_sess.add(user)
    db_sess.commit()


if __name__ == '__main__':
    main()