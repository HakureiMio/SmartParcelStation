from gateway.db.base import Base
from gateway.db.session import engine
from gateway.models import entities  # noqa: F401
from sqlalchemy import text


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        parcel_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(local_parcels)"))}
        parcel_additions = {
            "receiver_name_masked": "ALTER TABLE local_parcels ADD COLUMN receiver_name_masked VARCHAR(128)",
            "shelf_code": "ALTER TABLE local_parcels ADD COLUMN shelf_code VARCHAR(64)",
            "origin": "ALTER TABLE local_parcels ADD COLUMN origin VARCHAR(64) DEFAULT 'LOCAL_ONLY'",
            "sync_status": "ALTER TABLE local_parcels ADD COLUMN sync_status VARCHAR(64) DEFAULT 'LOCAL_ONLY'",
        }
        for column, statement in parcel_additions.items():
            if column not in parcel_columns:
                conn.execute(text(statement))

        tag_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(local_tags)"))}
        tag_additions = {
            "tag_uid": "ALTER TABLE local_tags ADD COLUMN tag_uid VARCHAR(128)",
            "hw_model": "ALTER TABLE local_tags ADD COLUMN hw_model VARCHAR(128)",
            "fw_version": "ALTER TABLE local_tags ADD COLUMN fw_version VARCHAR(64)",
            "ble_address": "ALTER TABLE local_tags ADD COLUMN ble_address VARCHAR(64)",
            "battery_mv": "ALTER TABLE local_tags ADD COLUMN battery_mv INTEGER",
            "registered_at": "ALTER TABLE local_tags ADD COLUMN registered_at DATETIME",
            "last_error_type": "ALTER TABLE local_tags ADD COLUMN last_error_type VARCHAR(64)",
            "last_error_message": "ALTER TABLE local_tags ADD COLUMN last_error_message TEXT",
            "last_error_at": "ALTER TABLE local_tags ADD COLUMN last_error_at DATETIME",
        }
        for column, statement in tag_additions.items():
            if column not in tag_columns:
                conn.execute(text(statement))

        binding_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(local_parcel_tag_bindings)"))}
        binding_additions = {
            "released_at": "ALTER TABLE local_parcel_tag_bindings ADD COLUMN released_at DATETIME",
            "release_reason": "ALTER TABLE local_parcel_tag_bindings ADD COLUMN release_reason VARCHAR(128)",
            "last_wake_session_id": "ALTER TABLE local_parcel_tag_bindings ADD COLUMN last_wake_session_id VARCHAR(64)",
            "last_wake_color": "ALTER TABLE local_parcel_tag_bindings ADD COLUMN last_wake_color VARCHAR(32)",
            "last_wake_at": "ALTER TABLE local_parcel_tag_bindings ADD COLUMN last_wake_at DATETIME",
        }
        for column, statement in binding_additions.items():
            if column not in binding_columns:
                conn.execute(text(statement))


if __name__ == "__main__":
    init_db()
