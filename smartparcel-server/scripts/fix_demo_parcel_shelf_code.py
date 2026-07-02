"""Idempotently repair shelf codes for the two deterministic demo parcels."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import SessionLocal, engine
from app.models.models import Parcel


EXPECTED_SHELVES = {
    'DEMO-PARCEL-0001': 'A03',
    'DEMO-PARCEL-0002': 'B01',
}


async def repair_demo_shelves() -> int:
    updated = 0
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(Parcel).where(Parcel.parcel_code.in_(EXPECTED_SHELVES))
        )).scalars().all()
        by_code = {row.parcel_code: row for row in rows}

        for parcel_code, expected_shelf in EXPECTED_SHELVES.items():
            parcel = by_code.get(parcel_code)
            if parcel is None:
                print(f'{parcel_code}: not found; skipped')
                continue
            before = parcel.shelf_code
            if before is None or not before.strip():
                parcel.shelf_code = expected_shelf
                updated += 1
                print(f'{parcel_code}: {before!r} -> {expected_shelf}')
            else:
                print(f'{parcel_code}: {before!r}; unchanged')

        await db.commit()

        repaired = (await db.execute(
            select(Parcel).where(Parcel.parcel_code.in_(EXPECTED_SHELVES)).order_by(Parcel.parcel_code)
        )).scalars().all()
        print('Final values:')
        for parcel in repaired:
            print(f'  {parcel.parcel_code}: shelf_code={parcel.shelf_code!r}')
    return updated


async def main() -> None:
    updated = await repair_demo_shelves()
    print(f'Updated rows: {updated}')
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
