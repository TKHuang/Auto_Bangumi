"""Rename system for organizing downloaded anime files.

Pure functions generate rename commands, orchestrator executes via interpreter.
Idempotent operations ensure crash safety and consistency.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from zen_bangumi.domain.commands.base import RenameFile
from zen_bangumi.domain.models.bangumi import Bangumi
from zen_bangumi.domain.models.torrent import Torrent
from zen_bangumi.domain.parser.bangumi_parser import BangumiParser
from zen_bangumi.effects.interpreter import EffectInterpreter
from zen_bangumi.effects.result import EffectResult
from zen_bangumi.repositories.bangumi import BangumiRepository
from zen_bangumi.repositories.torrent import TorrentRepository

logger = logging.getLogger(__name__)


@dataclass
class RenameResult:
    """Result of rename operation."""

    bangumi_id: int
    renamed_count: int = 0
    errors: list[str] = field(default_factory=list)


def gen_save_path(bangumi: Bangumi, base_path: str = "/downloads/Bangumi") -> str:
    """Generate save path for bangumi.
    
    Format: {base_path}/{title} ({year})/Season {N}/
    or: {base_path}/{title}/Season {N}/ (if no year)
    
    Args:
        bangumi: Bangumi model
        base_path: Base download directory
        
    Returns:
        Full save path string
    """
    if bangumi.year:
        folder = f"{bangumi.official_title} ({bangumi.year})"
    else:
        folder = bangumi.official_title
        
    save_path = Path(base_path) / folder / f"Season {bangumi.season}"
    return str(save_path)


def gen_rename_path(
    bangumi: Bangumi,
    episode: int | float,
    extension: str,
    version: int | None = None,
    episode_type: str | None = None,
    method: str = "pn",
) -> str:
    """Generate target filename for renamed file.
    
    Format: {title} S{season:02d}E{episode:02d}{version}.{ext}
    Special: {title} {type} {episode}{version}.{ext} (for OVA/OAD/SP)
    
    Args:
        bangumi: Bangumi model
        episode: Episode number (int or float)
        extension: File extension (e.g., ".mp4")
        version: Version number (e.g., 2 for v2)
        episode_type: Special episode type ("OVA", "OAD", "SP")
        method: Rename method ("pn" or "advance")
        
    Returns:
        Target filename
    """
    title = bangumi.official_title
    season = bangumi.season
    
    # Format season and episode with zero padding
    season_str = f"{season:02d}"
    
    # Convert episode to int if it's a whole number
    if isinstance(episode, float) and episode == int(episode):
        episode = int(episode)
    
    if isinstance(episode, int):
        episode_str = f"{episode:02d}"
    else:
        episode_str = f"{episode:05.1f}".replace(".", "")
    
    # Add version suffix if present
    version_suffix = f"v{version}" if version else ""
    
    # Handle special episode types (OVA, OAD, SP)
    if episode_type:
        return f"{title} {episode_type} {episode_str}{version_suffix}{extension}"
    
    # Regular episode with S##E## format
    return f"{title} S{season_str}E{episode_str}{version_suffix}{extension}"


def generate_rename_commands(
    bangumi: Bangumi,
    torrents: list[Torrent],
    downloader_type: str,
    base_path: str = "/downloads/Bangumi",
) -> list[RenameFile]:
    """Generate rename commands for unrenamed torrents.
    
    Pure function - no side effects, no DB access, no network calls.
    
    Args:
        bangumi: Bangumi model
        torrents: List of unrenamed torrents
        downloader_type: "pikpak" or "qbittorrent"
        base_path: Base download directory
        
    Returns:
        List of RenameFile commands
    """
    commands: list[RenameFile] = []
    parser = BangumiParser()
    
    for torrent in torrents:
        # Skip if already renamed
        if torrent.renamed_at is not None:
            continue
        
        # Parse torrent name to extract episode info
        try:
            parsed = parser.raw_parse(torrent.name)
            
            if not parsed.episode:
                logger.warning(f"Could not extract episode from: {torrent.name}")
                continue
            
            # Extract file extension
            extension = Path(torrent.name).suffix
            if not extension:
                extension = ".mp4"
            
            # Generate source and target paths
            save_path = gen_save_path(bangumi, base_path)
            
            # Source path depends on downloader type
            if downloader_type == "pikpak":
                # PikPak uses cloud paths
                source_path = f"{save_path}/{torrent.name}"
            else:
                # qBittorrent uses local paths
                source_path = f"{save_path}/{torrent.name}"
            
            # Generate target filename
            target_filename = gen_rename_path(
                bangumi=bangumi,
                episode=parsed.episode,
                extension=extension,
                version=parsed.version,
                episode_type=parsed.episode_type.value if parsed.episode_type else None,
            )
            
            target_path = f"{save_path}/{target_filename}"
            
            # Create rename command
            command = RenameFile(
                source_path=source_path,
                target_path=target_path,
                downloader_type=downloader_type,
            )
            
            commands.append(command)
            
        except Exception as e:
            logger.error(f"Failed to parse torrent {torrent.name}: {e}")
            continue
    
    return commands


async def rename_bangumi(
    bangumi_id: int,
    bangumi_repo: BangumiRepository,
    torrent_repo: TorrentRepository,
    interpreter: EffectInterpreter,
    downloader_type: str = "qbittorrent",
    base_path: str = "/downloads/Bangumi",
) -> RenameResult:
    """Rename all unrenamed torrents for a bangumi.
    
    Orchestrator function - loads data, generates commands, executes via interpreter.
    
    Args:
        bangumi_id: Bangumi ID
        bangumi_repo: Bangumi repository
        torrent_repo: Torrent repository
        interpreter: Effect interpreter
        downloader_type: "pikpak" or "qbittorrent"
        base_path: Base download directory
        
    Returns:
        RenameResult with statistics
    """
    result = RenameResult(bangumi_id=bangumi_id)
    
    try:
        # Load bangumi
        bangumi = await bangumi_repo.get_by_id(bangumi_id)
        if not bangumi:
            result.errors.append(f"Bangumi {bangumi_id} not found")
            return result
        
        # Load unrenamed torrents
        torrents = await torrent_repo.get_unrenamed(bangumi_id)
        if not torrents:
            logger.debug(f"No unrenamed torrents for bangumi {bangumi_id}")
            return result
        
        # Generate rename commands (pure function)
        commands = generate_rename_commands(
            bangumi=bangumi,
            torrents=torrents,
            downloader_type=downloader_type,
            base_path=base_path,
        )
        
        if not commands:
            logger.debug(f"No rename commands generated for bangumi {bangumi_id}")
            return result
        
        # Execute commands via interpreter (idempotent)
        results = await interpreter.execute(commands)
        
        # Count successes and collect errors
        for effect_result in results:
            if effect_result.status == "success":
                result.renamed_count += 1
                
                # Mark torrent as renamed in DB
                # Find corresponding torrent by matching source path
                if isinstance(effect_result.command, RenameFile):
                    source_name = Path(effect_result.command.source_path).name
                    for torrent in torrents:
                        if torrent.name == source_name:
                            await torrent_repo.mark_renamed(
                                torrent_id=torrent.id,
                                file_count=1,
                                cloud_path=effect_result.command.target_path if downloader_type == "pikpak" else None,
                            )
                            break
                            
            elif effect_result.status == "failed":
                result.errors.append(effect_result.error or "Unknown error")
        
        logger.info(
            f"Renamed {result.renamed_count}/{len(commands)} files for bangumi {bangumi_id}"
        )
        
    except Exception as e:
        logger.error(f"Failed to rename bangumi {bangumi_id}: {e}")
        result.errors.append(str(e))
    
    return result


async def rename_all(
    bangumi_repo: BangumiRepository,
    torrent_repo: TorrentRepository,
    interpreter: EffectInterpreter,
    downloader_type: str = "qbittorrent",
    base_path: str = "/downloads/Bangumi",
) -> dict[int, RenameResult]:
    """Rename all unrenamed torrents for all bangumi.
    
    Processes each bangumi sequentially to avoid concurrency issues.
    
    Args:
        bangumi_repo: Bangumi repository
        torrent_repo: Torrent repository
        interpreter: Effect interpreter
        downloader_type: "pikpak" or "qbittorrent"
        base_path: Base download directory
        
    Returns:
        Dictionary mapping bangumi ID to RenameResult
    """
    results: dict[int, RenameResult] = {}
    
    # Get all active bangumi
    bangumi_list = await bangumi_repo.get_active()
    
    for bangumi in bangumi_list:
        result = await rename_bangumi(
            bangumi_id=bangumi.id,
            bangumi_repo=bangumi_repo,
            torrent_repo=torrent_repo,
            interpreter=interpreter,
            downloader_type=downloader_type,
            base_path=base_path,
        )
        
        results[bangumi.id] = result
    
    # Log summary
    total_renamed = sum(r.renamed_count for r in results.values())
    total_errors = sum(len(r.errors) for r in results.values())
    
    logger.info(
        f"Rename batch complete: {total_renamed} files renamed, {total_errors} errors"
    )
    
    return results
