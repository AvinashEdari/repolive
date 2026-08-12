from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError

from app.core.config import Settings, get_settings
from app.observability import log_event


@dataclass(frozen=True)
class AuthUser:
    user_id: str
    email: str | None = None


class SupabaseTokenVerifier:
    """Verify Supabase access tokens against the project's rotating public keys."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.issuer = (
            f"{settings.supabase_url.rstrip('/')}/auth/v1" if settings.supabase_url else ""
        )
        self.jwks = (
            PyJWKClient(
                f"{self.issuer}/.well-known/jwks.json", timeout=settings.auth_jwks_timeout_seconds
            )
            if self.issuer
            else None
        )

    def verify(self, token: str) -> AuthUser:
        if self.jwks is None:
            raise HTTPException(status_code=503, detail="Authentication is not configured.")
        try:
            key = self.jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256", "ES256"],
                audience=self.settings.supabase_jwt_audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
        except PyJWTError as exc:
            log_event("authentication_failed", reason="invalid_or_expired_token", status=401)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise HTTPException(status_code=401, detail="Invalid access token subject.")
        email = claims.get("email")
        return AuthUser(subject, email if isinstance(email, str) else None)


@lru_cache
def get_token_verifier() -> SupabaseTokenVerifier:
    return SupabaseTokenVerifier(get_settings())


def get_optional_user(
    request: Request,
    verifier: Annotated[SupabaseTokenVerifier, Depends(get_token_verifier)],
) -> AuthUser | None:
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token:
        log_event("authentication_failed", reason="malformed_authorization", status=401)
        raise HTTPException(status_code=401, detail="A valid Bearer token is required.")
    return verifier.verify(token)


def require_user(user: Annotated[AuthUser | None, Depends(get_optional_user)]) -> AuthUser:
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
