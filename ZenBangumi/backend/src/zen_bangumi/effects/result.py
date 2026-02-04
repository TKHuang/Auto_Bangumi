from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EffectStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class EffectResult:
    command: object
    status: EffectStatus
    error: str | None = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.utcnow())
