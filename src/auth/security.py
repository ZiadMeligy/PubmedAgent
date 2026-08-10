from datetime import datetime, timedelta
import os
from pathlib import Path
import secrets
from typing import Optional
from jose import jwt
import bcrypt
from dotenv import load_dotenv


load_dotenv()


def _load_secret_key() -> str:
    """Load a deployment secret without shipping one in source control."""
    configured = os.getenv("JWT_SECRET_KEY")
    if configured:
        if len(configured) < 32:
            raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters")
        return configured

    # Local fallback: generate once and persist outside source control. Hospital
    # deployments should provide JWT_SECRET_KEY through their secret manager.
    secret_path = Path(__file__).resolve().parents[2] / "data" / ".jwt_secret"
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = secret_path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except FileNotFoundError:
        pass

    generated = secrets.token_urlsafe(64)
    try:
        descriptor = os.open(
            secret_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(generated)
        return generated
    except FileExistsError:
        return secret_path.read_text(encoding="utf-8").strip()


SECRET_KEY = _load_secret_key()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30 # 30 days

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
