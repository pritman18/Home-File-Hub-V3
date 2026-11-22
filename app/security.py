import hashlib
import secrets
import time
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

_password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)

def hash_password(password: str) -> str:
    return _password_hasher.hash(password)

def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False

def new_session():
    raw = secrets.token_urlsafe(40)
    csrf = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expires_at = int(time.time()) + 8 * 60 * 60
    return raw, token_hash, csrf, expires_at

def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
