"""PikPak cloud storage adapter for Command/Effect pattern.

Pure async implementation without threading or anyio portals.
Provides idempotent operations for torrent downloads and file management.
"""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

from pikpakapi import PikPakApi

from zen_bangumi.domain.commands.base import (
    CreateDirectory,
    DeleteTorrent,
    DownloadTorrent,
    RenameFile,
)
from zen_bangumi.effects.result import EffectResult, EffectStatus

logger = logging.getLogger(__name__)

# Regex pattern to extract torrent hash from magnet links
MAGNET_HASH_PATTERN = re.compile(r"urn:btih:([a-fA-F0-9]{40})", re.IGNORECASE)

# Token persistence file path
TOKEN_FILE = Path("data/pikpak_token.json")


class PikPakAdapter:
    """PikPak cloud storage adapter with idempotent operations.
    
    Pure async implementation for Command/Effect pattern.
    Handles token management, file operations, and torrent downloads.
    """

    def __init__(self, username: str, password: str):
        """Initialize PikPak adapter with credentials.
        
        Args:
            username: PikPak account username
            password: PikPak account password
        """
        self.username = username
        self.password = password
        self.client: PikPakApi | None = None
        self._token_data: dict[str, Any] | None = None

    async def _ensure_authenticated(self) -> None:
        """Ensure client is authenticated with valid token.
        
        Loads token from file if available, otherwise authenticates with credentials.
        Automatically refreshes expired tokens.
        """
        if self.client is None:
            self.client = PikPakApi(
                username=self.username,
                password=self.password,
            )

        # Try to load existing token
        if self._token_data is None and TOKEN_FILE.exists():
            try:
                with open(TOKEN_FILE, "r") as f:
                    self._token_data = json.load(f)
                    
                # Set token in client
                if "access_token" in self._token_data:
                    self.client.access_token = self._token_data["access_token"]
                if "refresh_token" in self._token_data:
                    self.client.refresh_token = self._token_data["refresh_token"]
                    
                logger.info("Loaded PikPak token from file")
            except Exception as e:
                logger.warning(f"Failed to load token: {e}")
                self._token_data = None

        # Authenticate if no valid token
        if not self.client.access_token:
            try:
                await self.client.login()
                self._save_token()
                logger.info("PikPak authentication successful")
            except Exception as e:
                logger.error(f"PikPak authentication failed: {e}")
                raise

    def _save_token(self) -> None:
        """Save current token to file for persistence."""
        if self.client and self.client.access_token:
            token_data = {
                "access_token": self.client.access_token,
                "refresh_token": self.client.refresh_token,
            }
            
            TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(TOKEN_FILE, "w") as f:
                json.dump(token_data, f)
                
            self._token_data = token_data
            logger.debug("Saved PikPak token to file")

    def _extract_hash(self, url: str) -> str | None:
        """Extract torrent hash from magnet link or URL.
        
        Args:
            url: Magnet link or torrent URL
            
        Returns:
            40-character hex hash, or None if not found
        """
        match = MAGNET_HASH_PATTERN.search(url)
        if match:
            return match.group(1).lower()
        return None

    async def _get_or_create_folder(self, path: str) -> str | None:
        """Get folder ID by path, creating if it doesn't exist.
        
        Args:
            path: Folder path (e.g., "/Bangumi/Title/Season 1")
            
        Returns:
            Folder ID, or None on error
        """
        try:
            await self._ensure_authenticated()
            
            # Split path into components
            parts = [p for p in path.split("/") if p]
            if not parts:
                return None
                
            # Start from root
            parent_id = ""
            
            # Create each folder in the path
            for part in parts:
                # List files in current folder
                files = await self.client.file_list(parent_id=parent_id)
                
                # Check if folder exists
                folder_id = None
                for file in files.get("files", []):
                    if file.get("name") == part and file.get("kind") == "drive#folder":
                        folder_id = file.get("id")
                        break
                
                # Create folder if it doesn't exist
                if not folder_id:
                    result = await self.client.create_folder(name=part, parent_id=parent_id)
                    folder_id = result.get("file", {}).get("id")
                    logger.info(f"Created PikPak folder: {part}")
                
                parent_id = folder_id
                
            return parent_id
            
        except Exception as e:
            logger.error(f"Failed to get/create folder {path}: {e}")
            return None

    async def download_torrent(self, command: DownloadTorrent) -> EffectResult:
        """Download torrent to PikPak cloud storage.
        
        Idempotent: Checks if torrent already exists before downloading.
        
        Args:
            command: DownloadTorrent command with URL and save path
            
        Returns:
            EffectResult with SUCCESS if downloaded/exists, FAILED on error
        """
        try:
            await self._ensure_authenticated()
            
            # Extract hash for idempotency check
            torrent_hash = self._extract_hash(command.torrent_url)
            if not torrent_hash:
                return EffectResult(
                    command=command,
                    status=EffectStatus.FAILED,
                    error="Could not extract torrent hash from URL",
                )
            
            # Check if torrent already exists (idempotency)
            try:
                tasks = await self.client.offline_list()
                for task in tasks.get("tasks", []):
                    task_hash = task.get("file_id", "").lower()
                    if torrent_hash in task_hash or task.get("name") == command.torrent_url:
                        logger.info(f"Torrent {torrent_hash[:8]} already exists in PikPak")
                        return EffectResult(
                            command=command,
                            status=EffectStatus.SKIPPED,
                            error="Torrent already exists",
                        )
            except Exception as e:
                logger.warning(f"Failed to check existing torrents: {e}")
            
            # Get or create target folder
            folder_id = await self._get_or_create_folder(command.save_path)
            if not folder_id:
                return EffectResult(
                    command=command,
                    status=EffectStatus.FAILED,
                    error=f"Failed to create folder: {command.save_path}",
                )
            
            # Add torrent
            result = await self.client.offline_download(
                url=command.torrent_url,
                parent_id=folder_id,
            )
            
            if result.get("task"):
                logger.info(f"Added torrent {torrent_hash[:8]} to PikPak")
                return EffectResult(
                    command=command,
                    status=EffectStatus.SUCCESS,
                )
            else:
                return EffectResult(
                    command=command,
                    status=EffectStatus.FAILED,
                    error="PikPak API returned no task",
                )
                
        except Exception as e:
            logger.error(f"Failed to download torrent: {e}")
            return EffectResult(
                command=command,
                status=EffectStatus.FAILED,
                error=str(e),
            )

    async def rename_file(self, command: RenameFile) -> EffectResult:
        """Rename file in PikPak cloud storage.
        
        Idempotent: Checks if target already exists before renaming.
        
        Args:
            command: RenameFile command with source and target paths
            
        Returns:
            EffectResult with SUCCESS if renamed/exists, FAILED on error
        """
        try:
            await self._ensure_authenticated()
            
            # Check if target already exists (idempotency)
            target_id = await self._find_file_by_path(command.target_path)
            if target_id:
                # Verify source is gone (already renamed)
                source_id = await self._find_file_by_path(command.source_path)
                if not source_id:
                    logger.info(f"File already renamed: {command.target_path}")
                    return EffectResult(
                        command=command,
                        status=EffectStatus.SKIPPED,
                        error="File already renamed",
                    )
            
            # Find source file
            source_id = await self._find_file_by_path(command.source_path)
            if not source_id:
                return EffectResult(
                    command=command,
                    status=EffectStatus.FAILED,
                    error=f"Source file not found: {command.source_path}",
                )
            
            # Extract new name from target path
            new_name = Path(command.target_path).name
            
            # Rename file
            await self.client.rename(file_id=source_id, name=new_name)
            logger.info(f"Renamed file: {command.source_path} -> {new_name}")
            
            return EffectResult(
                command=command,
                status=EffectStatus.SUCCESS,
            )
            
        except Exception as e:
            logger.error(f"Failed to rename file: {e}")
            return EffectResult(
                command=command,
                status=EffectStatus.FAILED,
                error=str(e),
            )

    async def create_directory(self, command: CreateDirectory) -> EffectResult:
        """Create directory in PikPak cloud storage.
        
        Idempotent: Checks if directory already exists before creating.
        
        Args:
            command: CreateDirectory command with path
            
        Returns:
            EffectResult with SUCCESS if created/exists, FAILED on error
        """
        try:
            folder_id = await self._get_or_create_folder(command.path)
            
            if folder_id:
                return EffectResult(
                    command=command,
                    status=EffectStatus.SUCCESS,
                )
            else:
                return EffectResult(
                    command=command,
                    status=EffectStatus.FAILED,
                    error="Failed to create directory",
                )
                
        except Exception as e:
            logger.error(f"Failed to create directory: {e}")
            return EffectResult(
                command=command,
                status=EffectStatus.FAILED,
                error=str(e),
            )

    async def delete_torrent(self, command: DeleteTorrent) -> EffectResult:
        """Delete torrent from PikPak cloud storage.
        
        Args:
            command: DeleteTorrent command with hash and delete_files flag
            
        Returns:
            EffectResult with SUCCESS if deleted, FAILED on error
        """
        try:
            await self._ensure_authenticated()
            
            # Find offline task by hash
            tasks = await self.client.offline_list()
            task_id = None
            
            for task in tasks.get("tasks", []):
                task_hash = task.get("file_id", "").lower()
                if command.torrent_hash.lower() in task_hash:
                    task_id = task.get("id")
                    break
            
            if not task_id:
                logger.warning(f"Torrent {command.torrent_hash[:8]} not found in PikPak")
                return EffectResult(
                    command=command,
                    status=EffectStatus.SKIPPED,
                    error="Torrent not found",
                )
            
            # Delete task
            await self.client.offline_task_delete(task_ids=[task_id], delete_files=command.delete_files)
            logger.info(f"Deleted torrent {command.torrent_hash[:8]} from PikPak")
            
            return EffectResult(
                command=command,
                status=EffectStatus.SUCCESS,
            )
            
        except Exception as e:
            logger.error(f"Failed to delete torrent: {e}")
            return EffectResult(
                command=command,
                status=EffectStatus.FAILED,
                error=str(e),
            )

    async def _find_file_by_path(self, path: str) -> str | None:
        """Find file ID by full path.
        
        Args:
            path: Full file path (e.g., "/Bangumi/Title/Season 1/Episode.mp4")
            
        Returns:
            File ID, or None if not found
        """
        try:
            await self._ensure_authenticated()
            
            # Split path into components
            parts = [p for p in path.split("/") if p]
            if not parts:
                return None
            
            # Navigate to parent folder
            parent_id = ""
            for part in parts[:-1]:
                files = await self.client.file_list(parent_id=parent_id)
                found = False
                
                for file in files.get("files", []):
                    if file.get("name") == part and file.get("kind") == "drive#folder":
                        parent_id = file.get("id")
                        found = True
                        break
                
                if not found:
                    return None
            
            # Find file in parent folder
            filename = parts[-1]
            files = await self.client.file_list(parent_id=parent_id)
            
            for file in files.get("files", []):
                if file.get("name") == filename:
                    return file.get("id")
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to find file {path}: {e}")
            return None

    async def get_file_info(self, path: str) -> dict[str, Any] | None:
        """Get file information by path.
        
        Args:
            path: Full file path
            
        Returns:
            File info dict, or None if not found
        """
        try:
            file_id = await self._find_file_by_path(path)
            if not file_id:
                return None
            
            await self._ensure_authenticated()
            result = await self.client.file_info(file_id=file_id)
            return result.get("file")
            
        except Exception as e:
            logger.error(f"Failed to get file info for {path}: {e}")
            return None

    async def list_files(self, path: str) -> list[dict[str, Any]]:
        """List files in directory.
        
        Args:
            path: Directory path
            
        Returns:
            List of file info dicts
        """
        try:
            folder_id = await self._get_or_create_folder(path)
            if not folder_id:
                return []
            
            await self._ensure_authenticated()
            result = await self.client.file_list(parent_id=folder_id)
            return result.get("files", [])
            
        except Exception as e:
            logger.error(f"Failed to list files in {path}: {e}")
            return []
