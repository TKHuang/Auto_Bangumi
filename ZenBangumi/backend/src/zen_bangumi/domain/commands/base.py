import hashlib
from dataclasses import dataclass
from typing import Protocol


class Command(Protocol):
    @property
    def idempotency_key(self) -> str:
        ...


@dataclass(frozen=True)
class DownloadTorrent:
    torrent_url: str
    save_path: str
    bangumi_id: int

    @property
    def idempotency_key(self) -> str:
        return f"download:{hashlib.sha256(self.torrent_url.encode()).hexdigest()}"


@dataclass(frozen=True)
class RenameFile:
    source_path: str
    target_path: str
    downloader_type: str

    @property
    def idempotency_key(self) -> str:
        return f"rename:{self.source_path}:{self.target_path}"


@dataclass(frozen=True)
class SendNotification:
    title: str
    message: str
    poster_url: str | None = None

    @property
    def idempotency_key(self) -> str:
        return f"notify:{hashlib.sha256(f'{self.title}:{self.message}'.encode()).hexdigest()}"


@dataclass(frozen=True)
class FetchTMDBInfo:
    title: str
    season: int

    @property
    def idempotency_key(self) -> str:
        return f"tmdb:{self.title}:s{self.season}"


@dataclass(frozen=True)
class CreateDirectory:
    path: str

    @property
    def idempotency_key(self) -> str:
        return f"mkdir:{self.path}"


@dataclass(frozen=True)
class DeleteTorrent:
    torrent_hash: str
    delete_files: bool = False

    @property
    def idempotency_key(self) -> str:
        return f"delete:{self.torrent_hash}:{self.delete_files}"
