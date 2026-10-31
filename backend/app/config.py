from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./data.db"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    DEBUG: bool = False
    UPLOAD_DIR: str = "./uploads"

    model_config = {"env_file": ".env"}


settings = Settings()


_WEAK_KEYS = {"dev-secret-key-change-in-production", "change-me", "secret", ""}


def ensure_secret_key(settings: Settings = None) -> None:
    """生产模式守卫：DEBUG=false 时弱/默认 SECRET_KEY 直接拒绝启动。"""
    s = settings or globals()["settings"]
    if s.DEBUG:
        return
    if s.SECRET_KEY.strip().lower() in _WEAK_KEYS or len(s.SECRET_KEY) < 32:
        raise RuntimeError(
            "SECRET_KEY 不安全：生产模式（DEBUG=false）要求 32 位以上强随机密钥。"
            "生成方式：python -c \"import secrets; print(secrets.token_hex(32))\"。"
            "或开发调试请显式设置 DEBUG=true。"
        )


settings = Settings()
ensure_secret_key(settings)
