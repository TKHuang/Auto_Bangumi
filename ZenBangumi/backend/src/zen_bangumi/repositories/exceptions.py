"""Repository layer exceptions."""


class ConcurrentModificationError(Exception):
    """Raised when optimistic locking detects a version mismatch."""

    def __init__(self, entity_type: str, entity_id: int, expected_version: int):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.expected_version = expected_version
        super().__init__(
            f"{entity_type} {entity_id} was modified by another transaction "
            f"(expected version {expected_version})"
        )
