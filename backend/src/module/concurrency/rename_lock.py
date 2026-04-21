"""Process-wide rename lock shared by scheduler jobs and manual APIs."""

from __future__ import annotations

import asyncio
from typing import Optional

_rename_lock = asyncio.Lock()


async def try_acquire_rename_lock() -> Optional[asyncio.Lock]:
    """Acquire the shared rename lock or return None if it is already held."""
    if _rename_lock.locked():
        return None
    await _rename_lock.acquire()
    return _rename_lock
