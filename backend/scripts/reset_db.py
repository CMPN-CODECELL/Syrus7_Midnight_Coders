import asyncio

from app.database.database import SessionLocal, check_connection, create_tables, drop_tables, engine
from app.database.seed import seed_defaults


async def main() -> None:
    await check_connection()
    await drop_tables()
    await create_tables()
    async with SessionLocal() as session:
        await seed_defaults(session)
    await engine.dispose()
    print("Database reset and seeded.")


if __name__ == "__main__":
    asyncio.run(main())