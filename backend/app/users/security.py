import secrets

import jwt
import datetime
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher


from app.core.config import settings
from app.users.model import utc_now

PasswordHasher = PasswordHash((Argon2Hasher(),))
Algorithm = settings.ALGORITHM

def hash_password(password: str) -> str:
    return PasswordHasher.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    verified,_ = PasswordHasher.verify_and_update(password, hashed_password)
    return verified

def create_access_token(data: str) -> str:
    expire = utc_now() + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload={
        "sub" : data,
        "exp": expire
    }
    
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=Algorithm)

def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[Algorithm])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    
def gen_handover_token() -> str:
    return secrets.token_urlsafe(8) 
    