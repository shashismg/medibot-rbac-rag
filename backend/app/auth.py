"""Demo authentication: 5 users (one per role), bcrypt-hashed passwords, role-tagged JWTs.

The role used for every RBAC decision is read from the signed token — never from the request body.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.rbac import ROLES


@dataclass(frozen=True)
class User:
    username: str
    display_name: str
    role: str
    password_hash: bytes


# Demo accounts (username, display name, role, password). Passwords are hashed at startup and
# the plaintext is only kept here because these are published demo credentials (see README).
_DEMO_USERS = [
    ("dr.mehta", "Dr. Arjun Mehta", "doctor", "doctor123"),
    ("nurse.priya", "Priya Sharma (RN)", "nurse", "nurse123"),
    ("billing.ravi", "Ravi Kumar", "billing_executive", "billing123"),
    ("tech.anand", "Anand Rao", "technician", "tech123"),
    ("admin.sys", "System Admin", "admin", "admin123"),
]


@lru_cache
def users() -> dict[str, User]:
    return {
        u: User(u, name, role, bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=10)))
        for u, name, role, pw in _DEMO_USERS
    }


def authenticate(username: str, password: str) -> User | None:
    user = users().get(username.strip().lower())
    if user and bcrypt.checkpw(password.encode(), user.password_hash):
        return user
    return None


def create_token(user: User) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user.username,
        "role": user.role,
        "name": user.display_name,
        "iat": now,
        "exp": now + timedelta(minutes=s.jwt_expire_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


@dataclass(frozen=True)
class CurrentUser:
    username: str
    role: str
    display_name: str


_bearer = HTTPBearer(auto_error=False)


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> CurrentUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token", headers={"WWW-Authenticate": "Bearer"})
    s = get_settings()
    try:
        claims = jwt.decode(creds.credentials, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}") from e
    role = claims.get("role")
    if role not in ROLES or claims.get("sub") not in users():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token claims")
    return CurrentUser(username=claims["sub"], role=role, display_name=claims.get("name", claims["sub"]))
