from pydantic import model_validator, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Any

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', case_sensitive=True)

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str
    DATABASE_URL: Optional[str] = None

    # Security settings
    SECRET_KEY: str = "a-very-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    @model_validator(mode='before')
    def assemble_db_connection(cls, v: Any) -> Any:
        if isinstance(v, dict) and 'DATABASE_URL' not in v:
            v['DATABASE_URL'] = str(PostgresDsn.build(
                scheme='postgresql',
                username=v.get('POSTGRES_USER'),
                password=v.get('POSTGRES_PASSWORD'),
                host=v.get('POSTGRES_SERVER'),
                port=int(v.get('POSTGRES_PORT') or 5432),
                path=f"{v.get('POSTGRES_DB') or ''}",
            ))
        return v

settings = Settings()

