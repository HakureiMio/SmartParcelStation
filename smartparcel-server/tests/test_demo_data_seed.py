import asyncio

from sqlalchemy import select

from app.models.enums import AccessCredentialStatus, ParcelStatus
from app.models.models import Gateway, GatewaySyncEvent, Parcel, UserAccessCredential
from app.services import services
from tests.stage1_helpers import create_schema, session_factory


def test_demo_seed_is_idempotent_and_has_two_waiting_parcels():
    async def scenario():
        engine, factory = session_factory(); await create_schema(engine)
        async with factory() as db:
            await services.ensure_default_users(db)
            db.add(Gateway(
                gateway_code='GW001', station_id=1,
                device_secret_hash='test-secret', status='ACTIVE',
            ))
            await db.commit()
            first = await services.ensure_demo_data(db)
            second = await services.ensure_demo_data(db)
            cards = (await db.execute(select(UserAccessCredential))).scalars().all()
            parcels = (await db.execute(select(Parcel).where(Parcel.status == ParcelStatus.WAITING_PICKUP))).scalars().all()
            assert first['parcel_ids'] == second['parcel_ids']
            assert len(cards) == 1 and cards[0].status == AccessCredentialStatus.ACTIVE
            assert len(parcels) == 2
            parcels_by_code = {parcel.parcel_code: parcel for parcel in parcels}
            assert parcels_by_code['DEMO-PARCEL-0001'].shelf_code == 'A03'
            assert parcels_by_code['DEMO-PARCEL-0002'].shelf_code == 'B01'

            parcel_events = (await db.execute(
                select(GatewaySyncEvent).where(GatewaySyncEvent.event_type == 'PARCEL_UPSERT')
            )).scalars().all()
            assert len(parcel_events) == 2
            for event in parcel_events:
                expected = 'A03' if event.payload_json['parcel_code'] == 'DEMO-PARCEL-0001' else 'B01'
                assert event.payload_json['shelf_code'] == expected
                assert event.payload_json['shelf'] == expected
        await engine.dispose()
    asyncio.run(scenario())


def test_demo_seed_repairs_missing_shelf_and_queues_parcel_upsert():
    async def scenario():
        engine, factory = session_factory(); await create_schema(engine)
        async with factory() as db:
            await services.ensure_default_users(db)
            db.add(Gateway(
                gateway_code='GW001', station_id=1,
                device_secret_hash='test-secret', status='ACTIVE',
            ))
            await db.commit()
            await services.ensure_demo_data(db)
            parcel = (await db.execute(
                select(Parcel).where(Parcel.parcel_code == 'DEMO-PARCEL-0001')
            )).scalar_one()
            parcel.shelf_code = None
            await db.commit()

            event_count_before = len((await db.execute(
                select(GatewaySyncEvent).where(GatewaySyncEvent.event_type == 'PARCEL_UPSERT')
            )).scalars().all())
            await services.ensure_demo_data(db)
            await db.refresh(parcel)
            assert parcel.shelf_code == 'A03'

            events = (await db.execute(
                select(GatewaySyncEvent).where(GatewaySyncEvent.event_type == 'PARCEL_UPSERT')
            )).scalars().all()
            assert len(events) == event_count_before + 1
            assert events[-1].payload_json['parcel_code'] == 'DEMO-PARCEL-0001'
            assert events[-1].payload_json['shelf_code'] == 'A03'
            assert events[-1].payload_json['shelf'] == 'A03'
        await engine.dispose()
    asyncio.run(scenario())
