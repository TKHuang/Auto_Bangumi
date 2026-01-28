"""PikPak cloud storage downloader client.

This module provides a synchronous wrapper around the async pikpakapi library,
enabling cloud-based torrent downloads as an alternative to qBittorrent.

Uses AnyIO for robust async/sync bridging with structured concurrency.
"""

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Any

import anyio
import requests
from anyio.from_thread import start_blocking_portal
from pikpakapi import PikPakApi

from module.ab_decorator import pikpak_retry
from module.conf import settings
from module.database import Database

logger = logging.getLogger(__name__)

# Regex pattern to extract torrent hash from magnet links
MAGNET_HASH_PATTERN = re.compile(r"urn:btih:([a-fA-F0-9]{40})", re.IGNORECASE)

# Token persistence file path (in /app/config volume)
TOKEN_FILE = "/app/config/pikpak_token.json"

# Hash map persistence file path (torrent hash -> cloud path)
HASH_MAP_FILE = "/app/config/pikpak_hash_map.json"

# Timeout for PikPak API calls in seconds (prevents hung requests blocking threads)
API_TIMEOUT_SECONDS = 60

# Maximum folder recursion depth to prevent infinite loops from circular references
MAX_FOLDER_DEPTH = 20

# PikPak phase type to qBittorrent-compatible state mapping
PHASE_STATE_MAP = {
    "PHASE_TYPE_PENDING": "stalledDL",
    "PHASE_TYPE_RUNNING": "downloading",
    "PHASE_TYPE_COMPLETE": "completed",
    "PHASE_TYPE_ERROR": "error",
}


@dataclass
class TorrentFile:
    """File entry within a torrent, compatible with qBittorrent file objects."""

    name: str


@dataclass
class TorrentInfo:
    """Torrent info compatible with qBittorrent torrent API responses.

    Provides attribute access similar to qbittorrent-api TorrentDictionary,
    enabling compatibility with existing renamer and status manager code.
    """

    hash: str
    name: str
    state: str
    progress: float
    save_path: str
    files: list[TorrentFile] = None

    def __post_init__(self):
        if self.files is None:
            self.files = []


class PikPakDownloader:
    """PikPak cloud storage downloader with async/sync bridge.

    Wraps the async pikpakapi library with synchronous methods for compatibility
    with AutoBangumi's synchronous downloader interface.

    Uses AnyIO's blocking portal for clean async/sync bridging with structured
    concurrency and level-triggered cancellation. A single persistent portal is
    maintained throughout the instance lifetime to ensure httpx connection pooling
    works correctly (connections are bound to a specific event loop).
    """

    # PikPak only supports URLs (magnet or torrent file URLs), not file uploads
    supports_torrent_files = False

    def __init__(self, username: str, password: str):
        """Initialize PikPak client with credentials.

        Attempts to load an existing token from file. If valid, uses it directly.
        If expired but refresh_token exists, will try to refresh on first API call.
        Otherwise, credentials will be used on first API call.
        Also loads any persisted hash-to-path mappings.

        Args:
            username: PikPak account email/username.
            password: PikPak account password.
        """
        self._username = username
        self._password = password
        self._client = PikPakApi(username=username, password=password)

        # Thread safety lock for async operations
        self._lock = threading.Lock()

        # Token expiration tracking (0 = not authenticated)
        self._token_expires_at: int = 0

        # Map of torrent hash -> cloud path for tracking downloads
        # Initialize empty first, then load from file (needs _lock to be set)
        self._hash_map: dict[str, str] = {}

        # Create persistent blocking portal for async operations.
        # This keeps a single event loop alive, allowing httpx connection pooling
        # to work correctly (connections are bound to the event loop).
        self._portal_context = start_blocking_portal()
        self._portal = self._portal_context.__enter__()

        # Try to load existing token
        token_data = self._load_token()
        if token_data:
            # Always load tokens if file exists - even if access token expired,
            # the refresh_token may still be valid for _ensure_valid_token to use
            self._client.access_token = token_data.get("access_token")
            self._client.refresh_token = token_data.get("refresh_token")
            self._client.user_id = token_data.get("user_id")
            self._client.encode_token()

            if self._is_token_valid(token_data):
                logger.info(f"Loaded valid PikPak token for user: {username}")
                self._token_expires_at = token_data.get("expires_at", 0)
            else:
                # Token expired, but refresh_token loaded - will refresh on first use
                logger.debug(
                    "PikPak access token expired, will refresh using refresh_token"
                )
                self._token_expires_at = 0  # Force refresh on first API call
        else:
            logger.debug("No PikPak token found, will authenticate on first use")

        # Load persisted hash map
        self._hash_map = self._load_hash_map()

    def __del__(self):
        """Clean up the blocking portal on destruction."""
        if hasattr(self, "_portal_context") and self._portal_context:
            try:
                self._portal_context.__exit__(None, None, None)
            except Exception:
                pass  # Ignore errors during cleanup

    def _run_async(self, coro: Any) -> Any:
        """Execute an async coroutine synchronously with thread safety.

        Uses the persistent blocking portal for clean async/sync bridging.
        This ensures all async operations run on the same event loop, allowing
        httpx connection pooling to work correctly.
        Uses a lock to prevent race conditions from concurrent API calls.
        Ensures token is valid before executing the operation.

        Args:
            coro: The coroutine to execute.

        Returns:
            The result of the coroutine execution.

        Raises:
            TimeoutError: If the operation exceeds API_TIMEOUT_SECONDS.
            Exception: Any exception raised by the coroutine.
        """
        with self._lock:
            # Ensure token is valid before making API calls
            self._ensure_valid_token()

            async def with_timeout():
                with anyio.fail_after(API_TIMEOUT_SECONDS):
                    return await coro

            try:
                return self._portal.call(with_timeout)
            except TimeoutError:
                raise TimeoutError(
                    f"PikPak API call timed out after {API_TIMEOUT_SECONDS}s"
                )

    def _load_token(self) -> dict | None:
        """Load authentication token from persistent storage.

        Returns:
            Token data dict with access_token, refresh_token, user_id, expires_at,
            or None if file doesn't exist or is invalid.
        """
        try:
            if os.path.exists(TOKEN_FILE):
                with open(TOKEN_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                    # Validate expected keys exist
                    if all(
                        k in data
                        for k in ["access_token", "refresh_token", "expires_at"]
                    ):
                        return data
                    logger.warning("PikPak token file missing required fields")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load PikPak token: {e}")
        return None

    def _save_token(self) -> None:
        """Save authentication token to persistent storage.

        Saves access_token, refresh_token, user_id, and expires_at (7200s from now)
        to the token file in JSON format. Also updates the internal expiration tracker.
        """
        expires_at = int(time.time()) + 7200  # Access token expires in 7200s
        self._token_expires_at = expires_at

        token_data = {
            "access_token": self._client.access_token,
            "refresh_token": self._client.refresh_token,
            "user_id": self._client.user_id,
            "expires_at": expires_at,
        }
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                json.dump(token_data, f, indent=2)
            logger.debug("PikPak token saved successfully")
        except OSError as e:
            logger.error(f"Failed to save PikPak token: {e}")

    def _load_hash_map(self) -> dict[str, str]:
        """Load torrent hash to cloud path mapping from persistent storage.

        Returns:
            Dictionary mapping torrent hashes to their cloud storage paths,
            or empty dict if file doesn't exist or is invalid.
        """
        try:
            if os.path.exists(HASH_MAP_FILE):
                with open(HASH_MAP_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        logger.debug(f"Loaded {len(data)} hash mappings from file")
                        return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load hash map: {e}")
        return {}

    def validate_hash_map(self) -> list[str]:
        """Validate hash map entries and remove those pointing to non-existent folders.

        Checks each path in the hash map and removes entries where the folder
        no longer exists in PikPak cloud storage.

        Returns:
            List of removed torrent hashes.
        """
        removed: list[str] = []

        with self._lock:
            hashes_to_check = list(self._hash_map.items())

        for torrent_hash, folder_path in hashes_to_check:
            try:
                # Ensure path starts with /
                if not folder_path.startswith("/"):
                    folder_path = f"/{folder_path}"

                path_info = self._run_async(
                    self._client.path_to_id(folder_path, create=False)
                )

                if not path_info:
                    logger.info(
                        f"Removing stale hash map entry: "
                        f"{torrent_hash[:8]}... -> {folder_path}"
                    )
                    with self._lock:
                        del self._hash_map[torrent_hash]
                    removed.append(torrent_hash)

            except Exception as e:
                logger.debug(f"Error validating path {folder_path}: {e}")

        if removed:
            with self._lock:
                self._save_hash_map()
            logger.info(f"Removed {len(removed)} stale hash map entries")

        return removed

    def _save_hash_map(self) -> None:
        """Save torrent hash to cloud path mapping to persistent storage."""
        try:
            os.makedirs(os.path.dirname(HASH_MAP_FILE), exist_ok=True)
            with open(HASH_MAP_FILE, "w", encoding="utf-8") as f:
                json.dump(self._hash_map, f, indent=2)
            logger.debug(f"Saved {len(self._hash_map)} hash mappings to file")
        except OSError as e:
            logger.error(f"Failed to save hash map: {e}")

    def _is_token_valid(self, token_data: dict) -> bool:
        """Check if the token is still valid (not expired).

        Args:
            token_data: Token data dict with expires_at timestamp.

        Returns:
            True if token has not expired, False otherwise.
        """
        expires_at = token_data.get("expires_at", 0)
        # Consider token invalid if it expires within 5 minutes
        valid = expires_at > (int(time.time()) + 300)
        return valid

    def _ensure_valid_token(self) -> None:
        """Ensure the access token is valid, refreshing if necessary.

        Called before API operations to prevent authentication failures.
        If the token is about to expire (within 5 minutes), performs a
        refresh using the refresh token. If refresh fails, re-authenticates.

        Uses the persistent blocking portal for async token operations.

        Raises:
            Exception: If both token refresh and re-authentication fail.
        """
        # Check if we need to refresh (within 5 minutes of expiry)
        if self._token_expires_at > int(time.time()) + 300:
            return  # Token is still valid

        if not self._client.refresh_token:
            # No refresh token, need full re-auth
            logger.info("No refresh token available, performing full authentication")
            self._portal.call(self._client.login)
            self._save_token()
            return

        try:
            logger.info("PikPak token expiring soon, refreshing...")
            self._portal.call(self._client.refresh_access_token)
            self._save_token()
            logger.info("PikPak token refreshed successfully")
        except Exception as e:
            logger.warning(f"Token refresh failed ({e}), attempting full re-auth")
            self._portal.call(self._client.login)
            self._save_token()

    @pikpak_retry(max_retries=3, initial_delay=10.0)
    def auth(self, validate_paths: bool = False) -> bool:
        """Authenticate with PikPak API.

        First checks if a valid token already exists (loaded from pikpak_token.json).
        If the token is still valid, returns True immediately without API call.
        Otherwise, calls the PikPak login API and saves the token on success.

        Includes retry logic for rate limiting and temporary failures.

        Args:
            validate_paths: If True, validate hash map entries after auth and
                remove entries pointing to non-existent folders.

        Returns:
            True if authentication succeeded (either existing token or new login).

        Raises:
            Exception: If login fails due to invalid credentials or network error.
        """
        # Check if we already have a valid token (loaded from file)
        # Token is valid if it expires more than 5 minutes from now
        if self._token_expires_at > int(time.time()) + 300:
            logger.info(
                f"PikPak: Using existing valid token for user {self._username} "
                f"(expires in {(self._token_expires_at - int(time.time())) // 60} min)"
            )
        else:
            logger.info(f"Authenticating PikPak user: {self._username}")
            with self._lock:
                self._portal.call(self._client.login)
            self._save_token()
            logger.info("PikPak authentication successful")

        # Optionally validate hash map entries after successful auth
        if validate_paths:
            try:
                self.validate_hash_map()
            except Exception as e:
                logger.warning(f"Hash map validation failed: {e}")

        return True

    def logout(self) -> None:
        """No-op for PikPak - tokens are preserved between operations.

        Unlike session-based downloaders (qBittorrent), PikPak uses OAuth tokens
        that should persist to avoid rate-limiting on frequent re-authentication.
        The token file is kept for reuse across operations.
        """
        # Intentionally do nothing - preserve tokens for reuse
        logger.debug("PikPak logout called (no-op, tokens preserved)")

    def check_host(self) -> bool:
        """Check if PikPak API server is reachable.

        Makes a simple HTTP request to verify network connectivity to PikPak.
        Does NOT authenticate - that happens separately in auth().

        Returns:
            True if PikPak API is reachable.
        """
        try:
            # Simple connectivity check - no auth required
            response = requests.get(
                "https://user.mypikpak.com/",
                timeout=5,
            )
            # Any response (even 404) means server is reachable
            logger.debug(f"PikPak API reachable (status: {response.status_code})")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"PikPak API not reachable: {e}")
            return False

    def _extract_hash(self, url: str) -> str | None:
        """Extract torrent hash from a magnet URL or torrent download URL.

        Supports:
        - Magnet links: magnet:?xt=urn:btih:<hash>
        - Mikan torrent URLs: https://mikanani.me/Download/YYYYMMDD/<hash>.torrent

        Args:
            url: A magnet link or torrent download URL.

        Returns:
            40-character lowercase hex hash, or None if not found.
        """
        # Try magnet link pattern first
        match = MAGNET_HASH_PATTERN.search(url)
        if match:
            return match.group(1).lower()

        # Try Mikan/torrent URL pattern: .../hash.torrent
        # Hash is 40 hex characters before .torrent
        torrent_match = re.search(r"/([a-fA-F0-9]{40})\.t", url)
        if torrent_match:
            return torrent_match.group(1).lower()

        return None

    def _get_or_create_folder(self, path: str) -> str | None:
        """Get or create nested folder structure in PikPak cloud.

        Creates all intermediate folders if they don't exist.

        Args:
            path: Folder path like "/downloads/Bangumi/Anime/SeriesName".

        Returns:
            Folder ID of the leaf folder, or None if creation fails.
        """
        # Ensure path starts with / for path_to_id
        if not path.startswith("/"):
            path = f"/{path}"

        logger.debug(f"Getting or creating folder: {path}")
        path_ids = self._run_async(self._client.path_to_id(path, create=True))

        if path_ids:
            folder_id = path_ids[-1].get("id")
            logger.debug(f"Folder ready: {path} -> {folder_id}")
            return folder_id

        logger.error(f"Failed to get or create folder: {path}")
        return None

    @pikpak_retry(max_retries=3, initial_delay=5.0)
    def add_torrents(
        self,
        torrent_urls: list[str] | str | None = None,
        torrent_files: list[bytes] | bytes | None = None,
        save_path: str = "",
        category: str | None = None,
        **kwargs: Any,
    ) -> bool:
        """Add torrent/magnet URLs for download to PikPak cloud.

        Interface matches QbDownloader.add_torrents() for compatibility.

        Args:
            torrent_urls: Magnet URL(s) to download. Can be a single URL string
                or a list of URLs.
            torrent_files: Ignored - PikPak doesn't support torrent file uploads,
                only magnet URLs.
            save_path: Destination folder path within configured download folder.
            category: Unused (PikPak uses folders, not categories).
            **kwargs: Additional arguments (ignored for compatibility).

        Returns:
            True if all downloads were added successfully.
            False if no URLs provided.

        Raises:
            Exception: If any download fails to start.
        """
        # Normalize URLs to a list
        if torrent_urls is None:
            if torrent_files is not None:
                logger.warning(
                    "[PikPak] Torrent files not supported, only magnet URLs. "
                    "Skipping download."
                )
            return False

        urls = [torrent_urls] if isinstance(torrent_urls, str) else torrent_urls

        if not urls:
            logger.warning("[PikPak] No URLs provided for download")
            return False

        # Use save_path directly (already includes settings.downloader.path from _gen_save_path)
        full_path = save_path

        # Create folder structure first
        folder_id = self._get_or_create_folder(full_path)
        if not folder_id:
            raise RuntimeError(f"Failed to create folder: {full_path}")

        # Collect hashes to track (extracted before API calls for safety)
        hashes_to_track: list[str] = []
        for url in urls:
            torrent_hash = self._extract_hash(url)
            if torrent_hash:
                hashes_to_track.append(torrent_hash.lower())
                logger.debug(f"Will track torrent hash: {torrent_hash}")
            else:
                logger.warning(f"Could not extract hash from URL: {url[:50]}...")

        # Delete any existing error/complete tasks for these hashes (enables redownload)
        if hashes_to_track:
            self._delete_existing_tasks_for_redownload(hashes_to_track)

        # Start all downloads
        for url in urls:
            logger.info(f"Adding download to PikPak: {url[:80]}...")
            result = self._run_async(
                self._client.offline_download(file_url=url, parent_id=folder_id)
            )
            logger.debug(f"Download added, result: {result}")

        # Update database with cloud path for each torrent
        with Database() as db:
            for torrent_hash in hashes_to_track:
                torrent_record = db.torrent.search_by_hash(torrent_hash)
                if torrent_record:
                    torrent_record.pikpak_cloud_path = full_path
                    db.torrent.update(torrent_record)
                    logger.debug(f"Stored PikPak path for {torrent_record.name}: {full_path}")
                else:
                    logger.debug(f"Torrent not found in DB for hash {torrent_hash[:16]}...")

        return True

    def _delete_existing_tasks_for_redownload(self, hashes: list[str]) -> None:
        """Delete existing offline tasks with error status to allow redownload.

        When user explicitly requests redownload, any existing task with the same
        hash (especially in error state like "file deleted") needs to be removed
        first before PikPak will accept a new download request.

        Args:
            hashes: List of lowercase torrent hashes to check for existing tasks.
        """
        if not hashes:
            return

        hash_set = set(hashes)

        try:
            # Get all offline tasks
            result = self._run_async(
                self._client.offline_list(
                    phase=[
                        "PHASE_TYPE_ERROR",
                        "PHASE_TYPE_COMPLETE",
                    ]
                )
            )

            tasks = result.get("tasks", [])
            tasks_to_delete: list[str] = []

            for task in tasks:
                file_url = task.get("file_url", "") or task.get("params", {}).get(
                    "url", ""
                )
                task_hash = self._extract_hash(file_url)

                if task_hash and task_hash.lower() in hash_set:
                    task_id = task.get("id")
                    phase = task.get("phase", "")

                    # Always delete error tasks (allows redownload)
                    # For complete tasks, check if files actually exist
                    if phase == "PHASE_TYPE_ERROR":
                        if task_id:
                            tasks_to_delete.append(task_id)
                            logger.info(
                                f"Will delete error task for redownload: {task_hash[:16]}..."
                            )
                    elif phase == "PHASE_TYPE_COMPLETE":
                        # Check if files still exist for this task
                        save_path = self._hash_map.get(task_hash.lower())
                        if save_path:
                            files = self._list_files_in_folder(save_path)
                            if not files:
                                # Files deleted, allow redownload
                                if task_id:
                                    tasks_to_delete.append(task_id)
                                    logger.info(
                                        f"Will delete task (files missing) for redownload: "
                                        f"{task_hash[:16]}..."
                                    )

            # Delete tasks in batch
            if tasks_to_delete:
                logger.info(
                    f"Deleting {len(tasks_to_delete)} existing tasks for redownload"
                )
                self._run_async(
                    self._client.delete_tasks(
                        task_ids=tasks_to_delete, delete_files=False
                    )
                )

        except Exception as e:
            logger.debug(f"Error checking/deleting existing tasks: {e}")
            # Continue with download attempt even if cleanup fails

    @pikpak_retry(max_retries=3, initial_delay=5.0)
    def torrents_info(
        self,
        status_filter: str | None = None,
        category: str | None = None,
        tag: str | None = None,
    ) -> list[TorrentInfo]:
        """Get info about offline download tasks in PikPak.

        Maps PikPak offline task phases to qBittorrent-compatible states.

        Args:
            status_filter: Filter by status (all, completed, downloading, etc.).
                          For PikPak, maps to phase types.
            category: Unused (PikPak uses folders, not categories).
            tag: Unused (PikPak doesn't support tags).

        Returns:
            List of TorrentInfo objects with hash, name, state, progress, save_path, files.
        """
        # Determine which phases to query based on status_filter
        if status_filter == "completed":
            phases = ["PHASE_TYPE_COMPLETE"]
        elif status_filter == "downloading":
            phases = ["PHASE_TYPE_RUNNING", "PHASE_TYPE_PENDING"]
        elif status_filter == "error":
            phases = ["PHASE_TYPE_ERROR"]
        else:
            # "all" or None - get all tasks
            phases = [
                "PHASE_TYPE_RUNNING",
                "PHASE_TYPE_ERROR",
                "PHASE_TYPE_COMPLETE",
                "PHASE_TYPE_PENDING",
            ]

        logger.debug(f"Fetching PikPak offline tasks with phases: {phases}")
        result = self._run_async(self._client.offline_list(phase=phases))

        tasks = result.get("tasks", [])
        torrents: list[TorrentInfo] = []

        for task in tasks:
            # Extract torrent hash from the original magnet URL
            file_url = task.get("file_url", "") or task.get("params", {}).get("url", "")
            torrent_hash = self._extract_hash(file_url)

            if not torrent_hash:
                # Try to extract from task ID or other fields
                task_id = task.get("id", "")
                torrent_hash = task_id[:40] if len(task_id) >= 40 else task_id

            # Map PikPak phase to qBittorrent-compatible state
            phase = task.get("phase", "")
            state = PHASE_STATE_MAP.get(phase, "unknown")

            # Calculate progress (0.0 to 1.0)
            progress = task.get("progress", 0)
            if isinstance(progress, int):
                progress = progress / 100.0

            # Get save path from database
            torrent_hash_lower = torrent_hash.lower() if torrent_hash else ""
            with Database() as db:
                torrent_record = db.torrent.search_by_hash(torrent_hash_lower)

            if torrent_record:
                save_path = torrent_record.pikpak_cloud_path
            else:
                save_path = None

            # Skip torrents without cloud path (not tracked in database)
            if not save_path:
                logger.warning(
                    f"Skipping torrent {task.get('name')} - no cloud path in database"
                )
                continue

            # Get file list for completed downloads (needed for Renamer)
            files: list[TorrentFile] = []
            # Check file existence for completed/error states
            logger.debug(
                f"Task {task.get('name')}: phase={phase}, state={state}, "
                f"save_path={save_path}"
            )
            if state == "completed" and save_path:
                # Only skip renamed torrents when fetching for rename cycle
                # (status_filter="completed"), not when fetching all for status display
                if status_filter == "completed":
                    # Check if already renamed - skip file listing entirely (saves API call!)
                    if torrent_record and torrent_record.renamed_at:
                        logger.debug(
                            f"Skipping already-renamed torrent: {task.get('name')}"
                        )
                        continue  # Skip this task entirely - don't add to result list

                    # Not renamed yet - list files for processing
                    files = self._list_files_in_folder(save_path)
                    logger.debug(f"Task {task.get('name')}: found {len(files)} files")
                    # If no files found, file was deleted from PikPak storage
                    if not files:
                        state = "missing"
                        logger.debug(
                            f"Task {task.get('name')} marked as missing - "
                            "files not found in PikPak storage"
                        )
            elif state == "error":
                # Only skip error tasks when fetching for rename cycle
                if status_filter == "completed":
                    logger.debug(
                        f"Skipping file listing for error task: {task.get('name')}"
                    )
                    # Error tasks have no files to rename, skip them entirely
                    continue

            torrent_info = TorrentInfo(
                hash=torrent_hash.lower() if torrent_hash else "",
                name=task.get("name", "Unknown"),
                state=state,
                progress=progress,
                save_path=save_path,
                files=files,
            )
            torrents.append(torrent_info)

        logger.debug(f"Found {len(torrents)} offline tasks in PikPak")
        return torrents

    def get_torrent_path(self, torrent_hash: str) -> str | None:
        """Get the cloud folder path for a torrent by its hash.

        Args:
            torrent_hash: 40-character hex torrent hash.

        Returns:
            Cloud path where the torrent was downloaded, or None if not found.
        """
        normalized_hash = torrent_hash.lower()
        path = self._hash_map.get(normalized_hash)

        if path:
            logger.debug(f"Found path for hash {normalized_hash}: {path}")
            return path

        # If not in memory, try to find from offline tasks
        logger.debug(f"Hash {normalized_hash} not in memory, searching offline tasks")
        torrents = self.torrents_info()
        for t in torrents:
            if t.hash == normalized_hash:
                logger.debug(f"Found path from offline task: {t.save_path}")
                return t.save_path

        logger.warning(f"Could not find path for torrent hash: {torrent_hash}")
        return None

    def _find_file_id_by_path(self, cloud_path: str) -> str | None:
        """Find a file ID by its full cloud path.

        Traverses the folder structure to locate the file.

        Args:
            cloud_path: Full path like "/downloads/Bangumi/Series/S01E01.mkv".

        Returns:
            File ID if found, None otherwise.
        """
        # Ensure path starts with /
        if not cloud_path.startswith("/"):
            cloud_path = f"/{cloud_path}"

        # Use path_to_id to resolve the path - it returns list of {id, name} dicts
        logger.debug(f"Looking up file ID for path: {cloud_path}")
        try:
            path_info = self._run_async(
                self._client.path_to_id(cloud_path, create=False)
            )
            if path_info:
                file_id = path_info[-1].get("id")
                logger.debug(f"Found file ID: {file_id} for path: {cloud_path}")
                return file_id
        except Exception as e:
            logger.debug(f"path_to_id failed for {cloud_path}: {e}")

        logger.warning(f"Could not find file ID for path: {cloud_path}")
        return None

    def _find_file_or_folder_id_by_name(
        self, parent_folder_path: str, name: str
    ) -> tuple[str | None, str]:
        """Find a file or folder ID by exact name match in parent folder.

        More reliable than path_to_id for similar filenames, especially
        with Chinese characters where path_to_id may return incorrect results.

        Args:
            parent_folder_path: Parent folder path (e.g., "AB" or "/AB").
            name: Exact filename or folder name to find.

        Returns:
            Tuple of (file_id, kind) where kind is 'drive#file' or 'drive#folder'.
            Returns (None, "") if not found.
        """
        # Ensure path starts with /
        if not parent_folder_path.startswith("/"):
            parent_folder_path = f"/{parent_folder_path}"

        logger.debug(
            f"Looking up file/folder by name: '{name}' in folder: {parent_folder_path}"
        )

        try:
            # Get folder ID first
            path_info = self._run_async(
                self._client.path_to_id(parent_folder_path, create=False)
            )
            if not path_info:
                logger.debug(f"Parent folder not found: {parent_folder_path}")
                return None, ""

            folder_id = path_info[-1].get("id")
            if not folder_id:
                return None, ""

            # List files in folder
            result = self._run_async(self._client.file_list(parent_id=folder_id))
            files = result.get("files", [])

            # Match by exact filename
            for f in files:
                if f.get("name") == name:
                    file_id = f.get("id")
                    kind = f.get("kind", "")
                    logger.debug(f"Found {kind}: id={file_id} for name='{name}'")
                    return file_id, kind

            logger.debug(f"File/folder not found: '{name}' in {parent_folder_path}")
            return None, ""

        except Exception as e:
            logger.debug(f"Error finding file by name: {e}")
            return None, ""

    def _list_files_in_folder(
        self,
        folder_path: str,
        _visited_ids: set[str] | None = None,
        _depth: int = 0,
    ) -> list[TorrentFile]:
        """List all files in a PikPak cloud folder.

        Recursively lists files, returning media/subtitle files for the Renamer.
        Includes cycle detection to prevent infinite recursion from circular
        folder references.

        Args:
            folder_path: Cloud folder path like "/downloads/Bangumi/Series Name/Season 1".
            _visited_ids: Internal set of already-visited folder IDs (for cycle detection).
            _depth: Internal recursion depth counter.

        Returns:
            List of TorrentFile objects with file names.
        """
        if _visited_ids is None:
            _visited_ids = set()

        # Safety: prevent infinite recursion
        if _depth > MAX_FOLDER_DEPTH:
            logger.warning(
                f"Max folder depth ({MAX_FOLDER_DEPTH}) exceeded at: {folder_path}"
            )
            return []

        files: list[TorrentFile] = []

        try:
            # Get folder ID from path
            if not folder_path.startswith("/"):
                folder_path = f"/{folder_path}"

            path_info = self._run_async(
                self._client.path_to_id(folder_path, create=False)
            )
            if not path_info:
                logger.debug(f"Folder not found: {folder_path}")
                return files

            # Validate we got the full path, not a partial match (stale path detection)
            returned_path = "/".join([p.get("name", "") for p in path_info])
            requested_path = folder_path.lstrip("/")

            if returned_path != requested_path:
                logger.warning(
                    f"Stale path detected: requested '{folder_path}' "
                    f"but PikPak only resolved to '/{returned_path}'. "
                    f"Folder may have been moved or deleted."
                )
                return files  # Fail fast - don't list wrong folder

            folder_id = path_info[-1].get("id")
            if not folder_id:
                return files

            # Cycle detection: skip if we've already visited this folder
            if folder_id in _visited_ids:
                logger.warning(
                    f"Circular folder reference detected: {folder_path} "
                    f"(folder_id={folder_id} already visited)"
                )
                return files

            _visited_ids.add(folder_id)

            # List files in the folder
            result = self._run_async(self._client.file_list(parent_id=folder_id))
            file_list = result.get("files", [])

            for f in file_list:
                file_name = f.get("name", "")
                file_kind = f.get("kind", "")

                # Include files (not folders)
                if file_kind == "drive#file":
                    files.append(TorrentFile(name=file_name))
                elif file_kind == "drive#folder":
                    # Recursively list files in subfolders
                    sub_path = f"{folder_path}/{file_name}"
                    sub_files = self._list_files_in_folder(
                        sub_path, _visited_ids, _depth + 1
                    )
                    # Prepend subfolder name to file paths
                    for sf in sub_files:
                        files.append(TorrentFile(name=f"{file_name}/{sf.name}"))

        except Exception as e:
            logger.debug(f"Error listing files in {folder_path}: {e}")

        return files

    def _list_all_file_ids_in_folder(
        self,
        folder_path: str,
        _visited_ids: set[str] | None = None,
        _depth: int = 0,
    ) -> list[str]:
        """Recursively collect all file IDs in a folder and its subfolders.

        Unlike _list_files_in_folder which returns TorrentFile objects,
        this returns the actual PikPak file IDs needed for move/delete operations.
        Includes cycle detection to prevent infinite recursion from circular
        folder references.

        Args:
            folder_path: Cloud folder path like "/downloads/Bangumi/Series Name/Season 1".
            _visited_ids: Internal set of already-visited folder IDs (for cycle detection).
            _depth: Internal recursion depth counter.

        Returns:
            List of file IDs for all files (not folders) in the tree.
        """
        if _visited_ids is None:
            _visited_ids = set()

        # Safety: prevent infinite recursion
        if _depth > MAX_FOLDER_DEPTH:
            logger.warning(
                f"Max folder depth ({MAX_FOLDER_DEPTH}) exceeded at: {folder_path}"
            )
            return []

        file_ids: list[str] = []

        try:
            # Ensure path starts with /
            if not folder_path.startswith("/"):
                folder_path = f"/{folder_path}"

            path_info = self._run_async(
                self._client.path_to_id(folder_path, create=False)
            )
            if not path_info:
                logger.debug(f"Folder not found: {folder_path}")
                return file_ids

            folder_id = path_info[-1].get("id")
            if not folder_id:
                return file_ids

            # Cycle detection: skip if we've already visited this folder
            if folder_id in _visited_ids:
                logger.warning(
                    f"Circular folder reference detected: {folder_path} "
                    f"(folder_id={folder_id} already visited)"
                )
                return file_ids

            _visited_ids.add(folder_id)

            # List files in the folder
            result = self._run_async(self._client.file_list(parent_id=folder_id))
            file_list = result.get("files", [])

            for f in file_list:
                file_id = f.get("id")
                file_kind = f.get("kind", "")
                file_name = f.get("name", "")

                if file_kind == "drive#file":
                    # It's a file - collect its ID
                    if file_id:
                        file_ids.append(file_id)
                elif file_kind == "drive#folder":
                    # It's a folder - recurse into it
                    sub_path = f"{folder_path}/{file_name}"
                    sub_ids = self._list_all_file_ids_in_folder(
                        sub_path, _visited_ids, _depth + 1
                    )
                    file_ids.extend(sub_ids)

        except Exception as e:
            logger.debug(f"Error listing file IDs in {folder_path}: {e}")

        return file_ids

    def _delete_empty_folder(
        self, folder_path: str, retries: int = 3, delay: float = 1.0
    ) -> bool:
        """Delete a folder if it's empty.

        Checks if the folder has any files or subfolders, and deletes it
        only if it's completely empty. Used for cleanup after move operations.

        Since PikPak's batch move is async, this method retries with delays
        to allow the move operation to complete before checking.

        Args:
            folder_path: Cloud folder path to check and potentially delete.
            retries: Number of times to retry if folder is not empty.
            delay: Seconds to wait between retries.

        Returns:
            True if folder was deleted or didn't exist, False if not empty.
        """
        import time

        # Ensure path starts with /
        if not folder_path.startswith("/"):
            folder_path = f"/{folder_path}"

        for attempt in range(retries):
            try:
                # Get folder ID
                path_info = self._run_async(
                    self._client.path_to_id(folder_path, create=False)
                )
                if not path_info:
                    logger.debug(f"Folder not found (already deleted?): {folder_path}")
                    return True

                folder_id = path_info[-1].get("id")
                if not folder_id:
                    return True

                # Check if folder is empty
                result = self._run_async(self._client.file_list(parent_id=folder_id))
                files = result.get("files", [])

                if files:
                    if attempt < retries - 1:
                        # PikPak move is async, wait and retry
                        logger.debug(
                            f"Folder not empty yet ({len(files)} items), "
                            f"waiting {delay}s for async move to complete... "
                            f"(attempt {attempt + 1}/{retries})"
                        )
                        time.sleep(delay)
                        continue
                    else:
                        logger.debug(
                            f"Folder not empty, skipping deletion: {folder_path} ({len(files)} items)"
                        )
                        return False

                # Folder is empty, delete it
                logger.info(f"Deleting empty source folder: {folder_path}")
                self._run_async(self._client.delete_to_trash(ids=[folder_id]))
                logger.debug(f"Successfully deleted empty folder: {folder_path}")
                return True

            except Exception as e:
                logger.debug(f"Error checking/deleting folder {folder_path}: {e}")
                return False

        return False

    @pikpak_retry(max_retries=3, initial_delay=5.0)
    def torrents_rename_file(
        self, torrent_hash: str, old_path: str, new_path: str
    ) -> bool:
        """Rename (and optionally move) a file in PikPak cloud storage.

        If old_path and new_path have different parent directories, the file
        will be moved to the target folder before renaming.

        Args:
            torrent_hash: Torrent hash to identify the download.
            old_path: Current file path relative to torrent folder.
            new_path: New file path relative to torrent folder.

        Returns:
            True on success or if file already has the correct name,
            False on conflict or file not found.
        """
        # Get the base path for this torrent
        base_path = self.get_torrent_path(torrent_hash)
        if not base_path:
            logger.warning(
                f"Cannot rename: torrent path not found for hash {torrent_hash}"
            )
            return False

        # Build full cloud paths
        full_old_path = f"{base_path}/{old_path}".replace("//", "/")
        full_new_path = f"{base_path}/{new_path}".replace("//", "/")

        logger.info(f"Renaming file in PikPak: {full_old_path} -> {full_new_path}")

        # Find the file ID for the old path
        file_id = self._find_file_id_by_path(full_old_path)
        if not file_id:
            logger.warning(f"File not found for rename: {full_old_path}")
            return False

        # Check if file needs to be moved to a different folder
        old_parent = os.path.dirname(full_old_path)
        new_parent = os.path.dirname(full_new_path)
        new_filename = os.path.basename(new_path)

        # If parents differ, we need to move the file first
        if old_parent != new_parent:
            logger.debug(f"File needs to be moved from {old_parent} to {new_parent}")
            target_folder_id = self._get_or_create_folder(new_parent)
            if not target_folder_id:
                logger.error(f"Failed to get/create target folder: {new_parent}")
                return False

            try:
                # Move the file to the target folder
                result = self._run_async(
                    self._client.file_batch_move(
                        ids=[file_id], to_parent_id=target_folder_id
                    )
                )
                logger.debug(f"Move result: {result}")
                logger.info(f"Moved file to: {new_parent}")

                # Try to clean up the source folder if it's now empty
                # This will only succeed after all files have been moved out
                self._delete_empty_folder(old_parent)
            except Exception as e:
                logger.error(f"Failed to move file in PikPak: {e}")
                return False

        # Now rename the file (it's now in the correct folder)
        try:
            result = self._run_async(
                self._client.file_rename(id=file_id, new_file_name=new_filename)
            )
            logger.debug(f"Rename result: {result}")
            logger.info(f"Successfully renamed file to: {new_filename}")
            return True
        except Exception as e:
            error_msg = str(e).lower()
            # "Name of file or folder is not changed" means file already has correct name
            # This can happen when multiple torrents share the same folder and one already
            # renamed the file. Treat this as success.
            if "not changed" in error_msg:
                logger.info(f"File already has correct name: {new_filename}")
                return True
            # "File name cannot be repeated" means a file with target name already exists
            # This is a naming conflict (e.g., parser generates same name for different files)
            # Don't trigger deletion - just warn and skip this file
            if "cannot be repeated" in error_msg or "name already exists" in error_msg:
                logger.warning(
                    f"File name conflict - '{new_filename}' already exists in folder. "
                    f"Skipping rename for: {os.path.basename(full_old_path)}"
                )
                return True  # Return True to prevent torrent deletion
            logger.error(f"Failed to rename file in PikPak: {e}")
            return False

    @pikpak_retry(max_retries=3, initial_delay=5.0)
    def torrents_delete(self, hashes: str | list[str]) -> None:
        """Delete torrents and their files from PikPak.

        Removes both the in-progress offline tasks (if any) and completed files
        from PikPak cloud storage. Idempotent - silently succeeds if the
        torrents/files are not found.

        Args:
            hashes: A single 40-character hex torrent hash or a list of hashes to delete.
        """
        # Normalize input to list
        if isinstance(hashes, str):
            hash_list = [hashes]
        else:
            hash_list = list(hashes)

        for torrent_hash in hash_list:
            self._delete_single_torrent(torrent_hash)

    def _delete_single_torrent(self, torrent_hash: str) -> None:
        """Delete a single torrent and its files from PikPak.

        Only removes the hash from tracking after verified successful deletion.
        This allows retry on failure.

        Args:
            torrent_hash: 40-character hex torrent hash to delete.
        """
        normalized_hash = torrent_hash.lower()
        logger.info(f"Deleting torrent from PikPak: {normalized_hash}")

        deletion_successful = False

        # First, try to find and delete the offline task
        try:
            # Get all offline tasks to find the matching task ID
            result = self._run_async(
                self._client.offline_list(
                    phase=[
                        "PHASE_TYPE_RUNNING",
                        "PHASE_TYPE_ERROR",
                        "PHASE_TYPE_COMPLETE",
                        "PHASE_TYPE_PENDING",
                    ]
                )
            )

            tasks = result.get("tasks", [])
            for task in tasks:
                # Check if this task matches the hash
                file_url = task.get("file_url", "") or task.get("params", {}).get(
                    "url", ""
                )
                task_hash = self._extract_hash(file_url)

                if task_hash and task_hash.lower() == normalized_hash:
                    task_id = task.get("id")
                    if task_id:
                        logger.debug(f"Found offline task {task_id} for hash, deleting")
                        self._run_async(
                            self._client.delete_tasks(
                                task_ids=[task_id], delete_files=True
                            )
                        )
                        deletion_successful = True
                        logger.info(
                            f"Deleted offline task for torrent: {normalized_hash}"
                        )
                    break

        except Exception as e:
            logger.debug(f"Error finding/deleting offline task: {e}")

        # If task was deleted with delete_files=True, we're done
        if deletion_successful:
            # Clean up hash map and persist (under lock for thread safety)
            with self._lock:
                if self._hash_map.pop(normalized_hash, None):
                    self._save_hash_map()
            return

        # If no task found, try to delete the completed file directly
        current_path = self.get_torrent_path(normalized_hash)
        if current_path:
            # Try to find and delete files for this torrent
            torrents = self.torrents_info()
            for t in torrents:
                if t.hash == normalized_hash:
                    file_path = f"{current_path}/{t.name}".replace("//", "/")
                    file_id = self._find_file_id_by_path(file_path)
                    if file_id:
                        try:
                            logger.debug(f"Deleting file {file_id} to trash")
                            self._run_async(self._client.delete_to_trash(ids=[file_id]))
                            deletion_successful = True
                            logger.info(
                                f"Deleted completed file for torrent: {normalized_hash}"
                            )
                        except Exception as e:
                            logger.debug(f"Error deleting file to trash: {e}")
                    break

        # Only clean up hash map if deletion was verified successful
        if deletion_successful:
            with self._lock:
                if self._hash_map.pop(normalized_hash, None):
                    self._save_hash_map()
            logger.debug(f"Torrent deletion complete for: {normalized_hash}")
        else:
            # Keep hash in map to allow retry
            logger.warning(
                f"Could not verify deletion for {normalized_hash}, keeping in hash map for retry"
            )

    @pikpak_retry(max_retries=3, initial_delay=5.0)
    def move_torrent(self, hashes: list[str], new_location: str) -> bool:
        """Move torrent files to a new location in PikPak cloud.

        Moves ALL files for each torrent (including multi-file torrents with
        subfolders) to the destination folder. After successful move, deletes
        empty source folders.

        Args:
            hashes: List of torrent hashes to move.
            new_location: Destination folder path.

        Returns:
            True on success.
        """
        logger.debug(
            f"[DEBUG] PikPak move_torrent called: hashes={hashes}, new_location={new_location}"
        )
        # Use new_location directly (already includes settings.downloader.path)
        full_path = new_location

        # Ensure destination folder exists
        dest_folder_id = self._get_or_create_folder(full_path)
        if not dest_folder_id:
            logger.error(f"Failed to create destination folder: {full_path}")
            return False

        # Collect file IDs to move (use set to avoid duplicates)
        file_ids: set[str] = set()
        hashes_to_update: list[str] = []
        source_folders_to_cleanup: set[str] = set()
        # Track which source folders we've already collected files from
        folders_collected: set[str] = set()

        for torrent_hash in hashes:
            normalized_hash = torrent_hash.lower()

            # Get the current path for this torrent
            current_path = self.get_torrent_path(normalized_hash)
            logger.debug(
                f"[DEBUG] move_torrent: hash={normalized_hash[:8]}..., current_path={current_path}"
            )
            if not current_path:
                logger.warning(
                    f"Cannot move: path not found for hash {normalized_hash}"
                )
                continue

            # Track source folder for cleanup after move
            source_folders_to_cleanup.add(current_path)

            # Find the torrent info to get the name
            torrents = self.torrents_info()
            torrent_name = None
            for t in torrents:
                if t.hash == normalized_hash:
                    torrent_name = t.name
                    break

            if not torrent_name:
                logger.warning(f"Cannot find torrent info for hash {normalized_hash}")
                continue

            # Use list-then-match approach for reliable file lookup
            # (path_to_id can return wrong results for similar Chinese filenames)
            logger.debug(
                f"[DEBUG] move_torrent: looking for '{torrent_name}' in '{current_path}'"
            )

            source_id, kind = self._find_file_or_folder_id_by_name(
                current_path, torrent_name
            )
            logger.debug(f"[DEBUG] move_torrent: source_id={source_id}, kind={kind}")

            if source_id:
                # Found file or folder by exact name match - move it directly
                file_ids.add(source_id)
                hashes_to_update.append(normalized_hash)
            else:
                # File not found by name (likely renamed). Collect ALL files from
                # source folder. Skip path_to_id fallback as it's unreliable for
                # Chinese filenames and can return folder IDs instead of file IDs.
                if current_path not in folders_collected:
                    logger.debug(
                        f"[DEBUG] move_torrent: file not found by name, collecting all files from '{current_path}'"
                    )
                    sub_ids = self._list_all_file_ids_in_folder(current_path)
                    logger.debug(f"[DEBUG] move_torrent: sub_ids from folder={sub_ids}")
                    if sub_ids:
                        file_ids.update(sub_ids)
                        folders_collected.add(current_path)
                    else:
                        logger.warning(f"No files found for torrent: {torrent_name}")
                else:
                    logger.debug(
                        f"[DEBUG] move_torrent: already collected files from '{current_path}'"
                    )
                hashes_to_update.append(normalized_hash)

        # Convert to list for API call
        file_ids_list = list(file_ids)
        logger.debug(
            f"[DEBUG] move_torrent: collected {len(file_ids_list)} unique file_ids, hashes_to_update={hashes_to_update}"
        )

        if not file_ids_list:
            logger.warning("No files found to move")
            return True  # No files to move is not an error

        # Move all files in one batch operation
        logger.info(f"Moving {len(file_ids_list)} files to: {full_path}")
        try:
            result = self._run_async(
                self._client.file_batch_move(
                    ids=file_ids_list, to_parent_id=dest_folder_id
                )
            )
            logger.debug(f"Move result: {result}")

            # Update hash map only after successful move
            with self._lock:
                for h in hashes_to_update:
                    self._hash_map[h] = full_path
                self._save_hash_map()

            logger.info(f"Successfully moved files to: {full_path}")

            # Clean up empty source folders
            for source_folder in source_folders_to_cleanup:
                # Don't delete if source and destination are the same
                if source_folder != full_path:
                    self._delete_empty_folder(source_folder)

            return True
        except Exception as e:
            logger.error(f"Failed to move files in PikPak: {e}")
            return False

    def get_existing_hashes(self, category: str | None = None) -> set:
        """Get all existing torrent hashes from PikPak offline tasks.

        Retrieves all offline download tasks and extracts the torrent hash
        from each task's magnet URL. Used by SeasonCollector to deduplicate
        before adding new downloads.

        Args:
            category: Unused parameter (PikPak uses folders, not categories).
                     Kept for API compatibility with QbDownloader.

        Returns:
            Set of lowercase 40-character hex torrent hashes.
        """
        try:
            # Fetch all offline tasks regardless of status
            result = self._run_async(
                self._client.offline_list(
                    phase=[
                        "PHASE_TYPE_RUNNING",
                        "PHASE_TYPE_ERROR",
                        "PHASE_TYPE_COMPLETE",
                        "PHASE_TYPE_PENDING",
                    ]
                )
            )

            tasks = result.get("tasks", [])
            hashes: set = set()

            for task in tasks:
                # Extract hash from the magnet URL in the task
                file_url = task.get("file_url", "") or task.get("params", {}).get(
                    "url", ""
                )
                torrent_hash = self._extract_hash(file_url)

                if torrent_hash:
                    hashes.add(torrent_hash.lower())

            logger.debug(f"Found {len(hashes)} existing torrent hashes in PikPak")
            return hashes

        except Exception as e:
            logger.warning(f"[Downloader] Failed to get existing hashes: {e}")
            return set()

    # =========================================================================
    # Stub Methods for API Compatibility
    # =========================================================================
    # The following methods are stubs required for interface compatibility with
    # QbDownloader. They are not applicable to PikPak since it handles these
    # operations differently or not at all.

    def rss_add_feed(self, url: str, item_path: str) -> None:
        """Stub: RSS feeds are managed independently by AutoBangumi.

        PikPak doesn't have built-in RSS functionality. AutoBangumi's RSS engine
        handles feed management directly without downloader integration.

        Args:
            url: RSS feed URL (ignored).
            item_path: Feed item path (ignored).
        """

    def rss_remove_item(self, item_path: str) -> None:
        """Stub: RSS items are managed independently by AutoBangumi.

        PikPak doesn't have built-in RSS functionality. AutoBangumi's RSS engine
        handles feed management directly without downloader integration.

        Args:
            item_path: Feed item path to remove (ignored).
        """

    def rss_get_feeds(self) -> dict:
        """Stub: RSS feeds are managed independently by AutoBangumi.

        PikPak doesn't have built-in RSS functionality. AutoBangumi's RSS engine
        handles feed management directly without downloader integration.

        Returns:
            Empty dict since PikPak has no RSS feeds.
        """
        return {}

    def rss_set_rule(self, rule_name: str, rule_def: dict) -> None:
        """Stub: RSS rules are managed independently by AutoBangumi.

        PikPak doesn't have built-in RSS rule functionality. AutoBangumi's RSS
        engine handles download rules directly without downloader integration.

        Args:
            rule_name: Rule name (ignored).
            rule_def: Rule definition dict (ignored).
        """

    def get_download_rule(self) -> dict:
        """Stub: Download rules are managed independently by AutoBangumi.

        PikPak doesn't have built-in RSS rule functionality. AutoBangumi's RSS
        engine handles download rules directly without downloader integration.

        Returns:
            Empty dict since PikPak has no RSS rules.
        """
        return {}

    def remove_rule(self, rule_name: str) -> None:
        """Stub: RSS rules are managed independently by AutoBangumi.

        PikPak doesn't have built-in RSS rule functionality. AutoBangumi's RSS
        engine handles download rules directly without downloader integration.

        Args:
            rule_name: Rule name to remove (ignored).
        """

    def prefs_init(self, prefs: dict) -> None:
        """Stub: PikPak has no configurable preferences via API.

        qBittorrent uses this to set download paths, speed limits, etc.
        PikPak configuration is done through account settings on their website.

        Args:
            prefs: Preferences dict (ignored).
        """

    def get_app_prefs(self) -> dict:
        """Return default preferences for API compatibility.

        Required by DownloadClient.init_downloader() when settings.downloader.path
        is empty. Returns a save_path pointing to the PikPak cloud folder.

        Returns:
            Dict with default save_path for PikPak cloud storage.
        """
        return {"save_path": settings.downloader.path}

    def add_category(self, category: str) -> None:
        """Stub: PikPak uses folders instead of categories.

        Category management is handled via folder creation in add_torrents()
        and _get_or_create_folder(). This method logs a debug message.

        Args:
            category: Category name (logged but not used).
        """
        logger.debug(f"PikPak uses folders instead of categories. Ignoring: {category}")

    def set_category(self, torrent_hash: str, category: str) -> None:
        """Stub: PikPak uses folders instead of categories.

        Torrents are organized by folder path, not categories. Moving files
        between folders should use move_torrent() instead.

        Args:
            torrent_hash: Torrent hash (ignored).
            category: Category name (logged but not used).
        """
        logger.debug(
            f"PikPak uses folders instead of categories. "
            f"Use move_torrent() to reorganize. Ignoring category: {category}"
        )

    def add_tag(self, torrent_hash: str, tag: str) -> None:
        """Stub: PikPak doesn't support tags on files.

        qBittorrent uses tags for organization. PikPak has no equivalent feature.

        Args:
            torrent_hash: Torrent hash (ignored).
            tag: Tag to add (ignored).
        """
