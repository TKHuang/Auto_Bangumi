import logging
import os
from typing import cast

from fastapi import Cookie, HTTPException, status

from module.conf import VERSION  # re-exported for tests that patch this name
from module.security.jwt import decode_access_token

logger = logging.getLogger(__name__)

# Auth is fully bypassed only when the operator explicitly sets AB_DEV_AUTH=1.
# Tying this to a build-time string (e.g. VERSION == "DEV_VERSION") used to
# silently expose every endpoint on any non-release docker image, so that path
# was removed.  `VERSION` is still imported above for backwards-compat with
# tests that monkeypatch `module.api.middleware.auth.VERSION` — patches now
# act as no-ops, which is the desired behavior when AB_DEV_AUTH is unset.
_DEV_AUTH_BYPASS = os.environ.get("AB_DEV_AUTH") == "1"
if _DEV_AUTH_BYPASS:
    logger.warning(
        "[auth] AB_DEV_AUTH=1 detected — every request will be authenticated as "
        "'admin' without any token. Never set this in production."
    )


async def get_current_user(token: str | None = Cookie(None)) -> str:
    if _DEV_AUTH_BYPASS:
        return "admin"

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = decode_access_token(token)
        username = payload.get("sub")
        if not username or not isinstance(username, str):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        return cast(str, username)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
