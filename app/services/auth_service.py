import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AuthService:
    """Client for AccessTokenDropbox microservice."""

    def __init__(self):
        self.token_service_url = settings.token_service_url
        self.api_secret_key = settings.api_secret_key
        self._cached_token: Optional[str] = None

    async def get_valid_token(self) -> str:
        """
        Retrieve a valid Dropbox access token from the auth microservice.
        The microservice handles token refresh automatically.
        """
        headers = {
            "Authorization": f"Bearer {self.api_secret_key}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.token_service_url}/token",
                    headers=headers
                )
                response.raise_for_status()

                data = response.json()
                token = data.get("access_token")

                if not token:
                    raise ValueError("No access_token in response")

                self._cached_token = token
                logger.info("Successfully retrieved Dropbox token from auth service")
                return token

            except httpx.HTTPStatusError as e:
                logger.error(f"Auth service HTTP error: {e.response.status_code}")
                raise
            except Exception as e:
                logger.error(f"Failed to get token from auth service: {e}")
                raise


auth_service = AuthService()
