from gateway.db.init_db import init_db
from gateway.db.session import engine


def test_init_db_creates_tables():
    init_db()
    tables = set(engine.dialect.get_table_names(engine.connect()))
    assert "local_parcels" in tables
    assert "gateway_tasks" in tables
    assert "sync_queue" in tables
