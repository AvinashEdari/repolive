import time

import httpx
import jwt

from app.core.config import Settings


class GitHubAppClient:
    """Least-privilege installation-token boundary; tokens are returned in memory only."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.github_app_id and self.settings.github_app_private_key)

    async def installation_token(self, installation_id: str) -> str:
        if not self.configured:
            raise RuntimeError("GitHub App is not configured.")
        private_key = self.settings.github_app_private_key
        if private_key is None:
            raise RuntimeError("GitHub App private key is unavailable.")
        now = int(time.time())
        app_jwt = jwt.encode(
            {"iat": now - 30, "exp": now + 540, "iss": self.settings.github_app_id},
            private_key.replace("\\n", "\n"),
            algorithm="RS256",
        )
        async with httpx.AsyncClient(base_url="https://api.github.com", timeout=10) as client:
            response = await client.post(
                f"/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        response.raise_for_status()
        token = response.json().get("token")
        if not isinstance(token, str):
            raise RuntimeError("GitHub App token response was malformed.")
        return token

    async def verify_user_installation(
        self, installation_id: str, user_access_token: str
    ) -> dict[str, str]:
        """Confirm the signed-in GitHub user can access this installation."""
        async with httpx.AsyncClient(base_url="https://api.github.com", timeout=10) as client:
            response = await client.get(
                f"/user/installations/{installation_id}",
                headers={
                    "Authorization": f"Bearer {user_access_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        response.raise_for_status()
        account = response.json().get("account")
        if not isinstance(account, dict):
            raise RuntimeError("GitHub installation response was malformed.")
        login, account_type = account.get("login"), account.get("type")
        if not isinstance(login, str) or not isinstance(account_type, str):
            raise RuntimeError("GitHub installation account was malformed.")
        return {"login": login, "account_type": account_type}
