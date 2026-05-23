import bcrypt

from app.models.user import User

DEMO_USERS = [
    {"username": "sales01", "display_name": "张三(销售)", "role": "sales"},
    {"username": "pm01", "display_name": "李四(项目经理)", "role": "pm"},
    {"username": "ops01", "display_name": "陈工(运营)", "role": "operations"},
    {"username": "proc01", "display_name": "王五(采购)", "role": "procurement"},
    {"username": "net01", "display_name": "刘工(网络工程师)", "role": "network_engineer"},
    {"username": "field01", "display_name": "孙工(现场实施)", "role": "field_engineer"},
]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def get_seed_users() -> list[User]:
    users = []
    hashed = hash_password("123456")
    for u in DEMO_USERS:
        users.append(User(
            username=u["username"],
            hashed_password=hashed,
            display_name=u["display_name"],
            role=u["role"],
        ))
    return users
