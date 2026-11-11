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
    DATABASE_URL: str

    # ===== 会话（服务端会话 + HttpOnly Cookie）=====
    # 未勾选"记住我"：服务端会话有效期（分钟），Cookie 为浏览器会话 Cookie，关浏览器即失效。
    SESSION_TTL_MINUTES: int = 720
    # 勾选"记住我"：服务端会话与 Cookie 的有效期（天）。
    SESSION_REMEMBER_DAYS: int = 30
    # 存放会话 ID 的 HttpOnly Cookie 名；生产 HTTPS 下可改为 "__Host-session"。
    SESSION_COOKIE_NAME: str = "session"
    # 存放 CSRF 令牌的 Cookie 名（非 HttpOnly，供前端读取后放进请求头）。
    CSRF_COOKIE_NAME: str = "csrf_token"
    # Cookie 是否只走 HTTPS；本地 http 开发为 false，生产必须为 true。
    COOKIE_SECURE: bool = False

    # 所有以文件形式存储的数据用下方函数寻址
    # @property
    # def invoice_dir(self) -> Path:
    #     return self.INVOICE_DIR if self.INVOICE_DIR.is_absolute() else BASE_DIR / self.INVOICE_DIR

    

settings = Settings() #type: ignore