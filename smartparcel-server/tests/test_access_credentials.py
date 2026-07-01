import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.enums import AccessCredentialType, UserRole
from app.models.models import Station, User
from app.services import services
from tests.stage1_helpers import create_schema, session_factory


def test_card_uid_cannot_be_reissued_to_another_user():
    async def scenario():
        engine, factory = session_factory()
        await create_schema(engine)
        async with factory() as db:
            db.add(Station(id=1, station_code='S1', name='S1', address='A'))
            staff = User(id=1, display_name='staff', role=UserRole.STAFF, station_id=1)
            first = User(id=2, display_name='u1', role=UserRole.USER, station_id=1)
            second = User(id=3, display_name='u2', role=UserRole.USER, station_id=1)
            db.add_all([staff, first, second]); await db.commit()
            await services.bind_user_card(db, first.id, 1, AccessCredentialType.CARD_UID, 'UID-1', None, staff)
            with pytest.raises(HTTPException) as exc:
                await services.bind_user_card(db, second.id, 1, AccessCredentialType.CARD_UID, 'UID-1', None, staff)
            assert exc.value.status_code == 409
        await engine.dispose()
    asyncio.run(scenario())
