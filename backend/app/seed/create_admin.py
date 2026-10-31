"""创建首个管理员账号（幂等保护：已存在 admin 时拒绝）。

用法：python -m app.seed.create_admin <username> <password>
"""
import asyncio
import sys

from sqlalchemy import select

from app.database import async_session
from app.models.user import User
from app.seed.seed_users import hash_password


async def create_admin(username: str, password: str) -> None:
    async with async_session() as db:
        exists = await db.execute(
            select(User).where(User.role == "admin", User.is_active == True)
        )
        if exists.scalar_one_or_none():
            print("已存在管理员账号，拒绝重复创建。如需重置密码请走「用户管理」页或数据库。")
            sys.exit(1)
        if len(password) < 8:
            print("密码至少 8 位。")
            sys.exit(1)
        db.add(User(
            username=username,
            hashed_password=hash_password(password),
            display_name=f"管理员({username})",
            role="admin",
            is_active=True,
        ))
        await db.commit()
        print(f"管理员 {username} 创建成功。请立即登录使用。")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法：python -m app.seed.create_admin <username> <password>")
        sys.exit(1)
    asyncio.run(create_admin(sys.argv[1], sys.argv[2]))
