import hashlib
import secrets

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

PasswordHasher = PasswordHash((Argon2Hasher(),))


def hash_password(password: str) -> str:
    """人类密码熵低，必须用 Argon2 这类加盐慢哈希抵抗暴力破解（FP-AUTH-2）。"""
    return PasswordHasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    verified, _ = PasswordHasher.verify_and_update(password, hashed_password)
    return verified


def new_random_token() -> str:
    """生成 256 位密码学安全随机串，用作会话 ID 或 CSRF 令牌。"""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """会话 ID 是服务端生成的 256 位随机串，SHA-256 即可防止库内明文泄露。

    这不是密码存储：密码熵低才需要加盐慢哈希；随机会话 ID 无法被穷举。
    """
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_equal(a: str, b: str) -> bool:
    """常量时间比较，避免通过响应耗时逐字符猜出令牌。"""
    return secrets.compare_digest(a.encode(), b.encode())


def gen_handover_token() -> str:
    return secrets.token_urlsafe(8)
