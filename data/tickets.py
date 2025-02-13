import sqlalchemy
from .db_session import SqlAlchemyBase
from flask_login import UserMixin
from sqlalchemy_serializer import SerializerMixin

from datetime import datetime


class Ticket(SqlAlchemyBase, UserMixin, SerializerMixin):
    __tablename__ = 'tickets'

    id = sqlalchemy.Column(
        sqlalchemy.Integer, primary_key=True, autoincrement=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    email = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    product_name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    problem_name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    problem_full = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    is_finished = sqlalchemy.Column(
        sqlalchemy.Boolean, nullable=True, default=False)
    worker = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    created_at = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=True, default=datetime.now)
    status = sqlalchemy.Column(sqlalchemy.Integer, nullable=True, default=0)
    chat_id = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    last_id = sqlalchemy.Column(sqlalchemy.Integer, nullable=True, default=0)
    assigned_to = sqlalchemy.Column(
        sqlalchemy.Integer, sqlalchemy.ForeignKey('users.id'), nullable=True)
