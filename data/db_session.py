import sqlalchemy as sa
import sqlalchemy.orm as orm
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

SqlAlchemyBase = orm.declarative_base()

__factory = None


def global_init(db_file):
    global __factory

    if __factory:
        return

    if not db_file or not db_file.strip():
        raise Exception("Необходимо указать файл базы данных.")

    conn_str = f'sqlite:///{db_file.strip()}?check_same_thread=False'
    print(f"Подключение к базе данных по адресу {conn_str}")

    engine = create_engine(conn_str,
                           poolclass=QueuePool,
                           pool_size=20,  # Увеличиваем размер пула
                           max_overflow=0,
                           pool_timeout=30)
    __factory = orm.sessionmaker(bind=engine)

    from . import __all_models

    SqlAlchemyBase.metadata.create_all(engine)


def create_session() -> Session:
    global __factory
    return __factory()
