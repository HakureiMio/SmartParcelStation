from gateway.db.base import Base
from gateway.db.session import engine
from gateway.models import entities  # noqa: F401
from sqlalchemy import text


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(local_parcels)"))}
        additions = {
            "receiver_name_masked": "ALTER TABLE local_parcels ADD COLUMN receiver_name_masked VARCHAR(128)",
            "origin": "ALTER TABLE local_parcels ADD COLUMN origin VARCHAR(64) DEFAULT 'LOCAL_ONLY'",
            "sync_status": "ALTER TABLE local_parcels ADD COLUMN sync_status VARCHAR(64) DEFAULT 'LOCAL_ONLY'",
        }
        for column, statement in additions.items():
            if column not in columns:
                conn.execute(text(statement))


if __name__ == "__main__":
    init_db()
