from gateway.db.base import Base
from gateway.db.session import engine
from gateway.models import entities  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
