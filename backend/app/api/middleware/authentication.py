from __future__ import annotations

from fastapi import Header

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """
    Protects admin routes when ADMIN_API_TOKEN is configured.

    Local development remains open by default. Production deployments should set
    ADMIN_API_TOKEN and pass it as X-Admin-Token from the frontend or API client.
    """

    expected_token = get_settings().api.admin_api_token
    if not expected_token:
        return

    if x_admin_token != expected_token:
        raise AuthenticationError(
            "A valid admin token is required",
            code="ADMIN_AUTH_REQUIRED",
        )
