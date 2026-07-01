import asyncio

from sqlalchemy import select

from app.models.enums import AccessCredentialStatus, ParcelStatus
from app.models.models import Parcel, UserAccessCredential
from app.services import services
from tests.stage1_helpers import create_schema, session_factory


def test_demo_seed_is_idempotent_and_has_two_waiting_parcels():
    async def scenario():
        engine, factory = session_factory(); await create_schema(engine)
        async with factory() as db:
            first = await services.ensure_demo_data(db)
            second = await services.ensure_demo_data(db)
            cards = (await db.execute(select(UserAccessCredential))).scalars().all()
            parcels = (await db.execute(select(Parcel).where(Parcel.status == ParcelStatus.WAITING_PICKUP))).scalars().all()
            assert first['parcel_ids'] == second['parcel_ids']
            assert len(cards) == 1 and cards[0].status == AccessCredentialStatus.ACTIVE
            assert len(parcels) == 2
        await engine.dispose()
    asyncio.run(scenario())
