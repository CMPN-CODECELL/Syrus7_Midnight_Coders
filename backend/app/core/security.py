from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any, Optional

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()
ALGORITHM = "HS256"
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Ensure HMAC key is at least 32 bytes per RFC 7518
JWT_SECRET_KEY = (
    settings.jwt_secret
    if len(settings.jwt_secret) >= 32
    else hashlib.sha256(settings.jwt_secret.encode()).hexdigest()
)


def hash_password(password: str) -> str:
    """Hash password securely using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(
    data: dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and validate signed JWT access token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None


def generate_reset_token() -> str:
    """Generate cryptographically secure single-use token for password reset."""
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """Hash reset token using SHA-256 for secure storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
