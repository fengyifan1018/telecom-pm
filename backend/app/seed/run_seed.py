"""
Seed the database with demo users and workflow templates.

Usage:
    python -m app.seed.run_seed
"""
import asyncio

from sqlalchemy import select

from app.database import async_session, engine, Base
from app.models import *  # noqa
from app.models.user import User
from app.models.project import Customer
from app.models.workflow_template import WorkflowTemplate
from app.seed.seed_users import get_seed_users
from app.seed.seed_templates import get_dia_template, get_transmission_template, get_dark_fiber_template, get_sdwan_template


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # Seed users
        existing = await db.execute(select(User).limit(1))
        if existing.first() is None:
            for user in get_seed_users():
                db.add(user)
            print("Seeded 6 demo users (password: 123456)")
        else:
            print("Users already exist, skipping")

        # Seed templates
        for product_type, getter, label in [
            ("dia", get_dia_template, "DIA"),
            ("transmission", get_transmission_template, "传输"),
            ("dark_fiber", get_dark_fiber_template, "裸纤"),
            ("sdwan", get_sdwan_template, "SD-WAN"),
        ]:
            existing = await db.execute(
                select(WorkflowTemplate).where(WorkflowTemplate.product_type == product_type)
            )
            if existing.first() is None:
                db.add(getter())
                print(f"Seeded {label} workflow template")
            else:
                print(f"{label} template already exists, skipping")

        # Seed a demo customer
        existing = await db.execute(select(Customer).limit(1))
        if existing.first() is None:
            db.add(Customer(name="XX科技有限公司", contact_name="王经理", contact_phone="13800138000"))
            db.add(Customer(name="YY银行", contact_name="张总", contact_phone="13900139000"))
            print("Seeded 2 demo customers")
        else:
            print("Customers already exist, skipping")

        await db.commit()
    print("Seed completed!")


if __name__ == "__main__":
    asyncio.run(seed())
