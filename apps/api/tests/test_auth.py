from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from app.auth import SupabaseTokenVerifier
from app.core.config import Settings


def configured_verifier() -> tuple[SupabaseTokenVerifier, rsa.RSAPrivateKey]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = SupabaseTokenVerifier(
        Settings(supabase_url="https://project.supabase.co", supabase_jwt_audience="authenticated")
    )
    verifier.jwks = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private_key.public_key())
    )
    return verifier, private_key


def access_token(
    private_key: rsa.RSAPrivateKey,
    *,
    audience: str = "authenticated",
    expires_in: timedelta = timedelta(minutes=5),
) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": "user-123",
            "email": "person@example.com",
            "aud": audience,
            "iss": "https://project.supabase.co/auth/v1",
            "iat": now,
            "exp": now + expires_in,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )


def test_valid_supabase_access_token_returns_minimal_user_identity() -> None:
    verifier, private_key = configured_verifier()
    user = verifier.verify(access_token(private_key))
    assert user.user_id == "user-123"
    assert user.email == "person@example.com"


@pytest.mark.parametrize(
    "token_factory",
    [
        lambda key: access_token(key, audience="another-project"),
        lambda key: access_token(key, expires_in=timedelta(minutes=-1)),
    ],
)
def test_invalid_or_expired_tokens_return_generic_unauthorized(
    token_factory: Callable[[rsa.RSAPrivateKey], str],
) -> None:
    verifier, private_key = configured_verifier()
    token = token_factory(private_key)
    with pytest.raises(HTTPException) as error:
        verifier.verify(token)
    assert error.value.status_code == 401
    assert error.value.detail == "Invalid or expired access token."
    assert token not in str(error.value.detail)


def test_authentication_without_supabase_configuration_is_unavailable() -> None:
    verifier = SupabaseTokenVerifier(Settings())
    with pytest.raises(HTTPException) as error:
        verifier.verify("not-a-token")
    assert error.value.status_code == 503
