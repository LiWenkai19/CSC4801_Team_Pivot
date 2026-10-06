from pydantic_settings import BaseSettings,SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    APP_NAME: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    DATABASE_URL: str

    # 所有以文件形式存储的数据用下方函数寻址
    # @property
    # def invoice_dir(self) -> Path:
    #     return self.INVOICE_DIR if self.INVOICE_DIR.is_absolute() else BASE_DIR / self.INVOICE_DIR

    

settings = Settings() #type: ignore