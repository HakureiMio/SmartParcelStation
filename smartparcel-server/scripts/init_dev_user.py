import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.enums import UserRole
from app.models.models import User


async def init_dev_user() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        result = await db.execute(select(User).where(User.id == 1))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                id=1,
                display_name='Dev Server Admin',
                role=UserRole.SERVER_ADMIN,
                is_active=True,
                phone='10000000001',
            )
            db.add(user)
            action = 'created'
        else:
            user.display_name = 'Dev Server Admin'
            user.role = UserRole.SERVER_ADMIN
            user.is_active = True
            if not user.phone:
                user.phone = '10000000001'
            action = 'updated'

        await db.commit()
        print(f'dev user {action}: id=1 role=SERVER_ADMIN active=true')

    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(init_dev_user())
