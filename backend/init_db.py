"""首次部署初始化：create_all 建全部基础表（幂等，已存在则跳过）。"""
import asyncio

from app.database import engine, Base
import app.models  # noqa: F401 注册全部模型


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[init_db] tables ensured.")


if __name__ == "__main__":
    asyncio.run(main())
