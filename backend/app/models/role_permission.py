from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    permission_key: Mapped[str] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(20))

    __table_args__ = (UniqueConstraint("permission_key", "role"),)
