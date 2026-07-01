import asyncio

from app.models.enums import AccessCredentialStatus, AccessCredentialType, UserRole
from app.models.models import Station, User
from app.services import services
from tests.stage1_helpers import create_schema, session_factory


def test_new_card_replaces_old_card():
    async def scenario():
        engine, factory = session_factory(); await create_schema(engine)
        async with factory() as db:
            db.add(Station(id=1, station_code='S1', name='S1', address='A'))
            staff = User(id=1, display_name='staff', role=UserRole.STAFF, station_id=1)
            user = User(id=2, display_name='user', role=UserRole.USER, station_id=1)
            db.add_all([staff, user]); await db.commit()
            old, _ = await services.bind_user_card(db, 2, 1, AccessCredentialType.CARD_UID, 'OLD', None, staff)
            new, replaced = await services.bind_user_card(db, 2, 1, AccessCredentialType.CARD_UID, 'NEW', None, staff)
            assert new.status == AccessCredentialStatus.ACTIVE
            assert replaced.id == old.id and replaced.status == AccessCredentialStatus.REPLACED
            assert replaced.replaced_by_id == new.id
        await engine.dispose()
    asyncio.run(scenario())
