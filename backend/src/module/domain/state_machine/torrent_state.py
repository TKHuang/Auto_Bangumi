"""Torrent lifecycle state machine.

This module defines the state machine for torrent lifecycle management,
including all valid states and transitions. The state machine validates
transitions before database updates and provides callbacks for event bus integration.

States:
    - PENDING: Initial state, torrent created but not queued
    - QUEUED: Torrent queued for download
    - DOWNLOADING: Actively downloading
    - COMPLETED: Download completed, ready for renaming
    - RENAMING: Renaming in progress
    - RENAMED: Renaming completed
    - ERROR: Error occurred during processing
    - STALE: Path invalid but task exists (recoverable)
    - MISSING: Files missing from storage (exhaustive search failed)

Transitions:
    - queue: PENDING → QUEUED
    - start_download: QUEUED → DOWNLOADING
    - complete: DOWNLOADING → COMPLETED
    - start_rename: COMPLETED → RENAMING
    - finish_rename: RENAMING → RENAMED
    - fail: (PENDING|QUEUED|DOWNLOADING|RENAMING) → ERROR
    - mark_stale: COMPLETED → STALE
    - recover: STALE → COMPLETED
    - mark_missing: (COMPLETED|STALE) → MISSING
    - retry: ERROR → PENDING
"""

from enum import Enum

from statemachine import State, StateMachine
from statemachine.exceptions import TransitionNotAllowed


class TorrentStateEnum(str, Enum):
    """Torrent state enumeration."""

    PENDING = "pending"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    RENAMING = "renaming"
    RENAMED = "renamed"
    ERROR = "error"
    STALE = "stale"
    MISSING = "missing"


class TorrentStateMachine(StateMachine):
    """State machine for torrent lifecycle management.

    This state machine validates all transitions and provides callbacks
    for event bus integration. It is synchronous - async side effects
    are handled by the event bus.

    Example:
        >>> sm = TorrentStateMachine()
        >>> sm.current_state
        <State('PENDING', ...)>
        >>> sm.queue()
        >>> sm.current_state.id
        'queued'
        >>> sm.start_download()
        >>> sm.complete()
        >>> sm.current_state.id
        'completed'
    """

    # Define states
    pending = State(TorrentStateEnum.PENDING, initial=True)
    queued = State(TorrentStateEnum.QUEUED)
    downloading = State(TorrentStateEnum.DOWNLOADING)
    completed = State(TorrentStateEnum.COMPLETED)
    renaming = State(TorrentStateEnum.RENAMING)
    renamed = State(TorrentStateEnum.RENAMED)
    error = State(TorrentStateEnum.ERROR)
    stale = State(TorrentStateEnum.STALE)
    missing = State(TorrentStateEnum.MISSING)

    # Define transitions
    queue = pending.to(queued)
    start_download = queued.to(downloading)
    complete = downloading.to(completed)
    start_rename = completed.to(renaming)
    finish_rename = renaming.to(renamed)

    # Error transition from multiple states
    fail = (
        pending.to(error)
        | queued.to(error)
        | downloading.to(error)
        | renaming.to(error)
    )

    # Stale/recovery transitions
    mark_stale = completed.to(stale)
    recover = stale.to(completed)

    # Missing transition from completed or stale
    mark_missing = completed.to(missing) | stale.to(missing)

    # Retry from error
    retry = error.to(pending)

    def on_enter_state(self, target: State, source: State) -> None:
        """Called when entering any state (for event bus integration)."""
        pass

    @classmethod
    def from_str(cls, state_string: str) -> "TorrentStateMachine":
        """Create a state machine instance from a state string.

        Args:
            state_string: State name (e.g., "pending", "completed")

        Returns:
            TorrentStateMachine instance in the specified state

        Raises:
            ValueError: If state_string is not a valid state

        Example:
            >>> sm = TorrentStateMachine.from_str("completed")
            >>> sm.current_state.id
            'completed'
        """
        # Validate state string
        try:
            state_enum = TorrentStateEnum(state_string.lower())
        except ValueError as e:
            valid_states = [s.value for s in TorrentStateEnum]
            raise ValueError(
                f"Invalid state '{state_string}'. Valid states: {valid_states}"
            ) from e

        # Create instance and transition to target state
        instance = cls()

        # Map of state enum to state object
        state_map = {
            TorrentStateEnum.PENDING: instance.pending,
            TorrentStateEnum.QUEUED: instance.queued,
            TorrentStateEnum.DOWNLOADING: instance.downloading,
            TorrentStateEnum.COMPLETED: instance.completed,
            TorrentStateEnum.RENAMING: instance.renaming,
            TorrentStateEnum.RENAMED: instance.renamed,
            TorrentStateEnum.ERROR: instance.error,
            TorrentStateEnum.STALE: instance.stale,
            TorrentStateEnum.MISSING: instance.missing,
        }

        target_state = state_map[state_enum]
        instance.current_state = target_state

        return instance


__all__ = [
    "TorrentStateMachine",
    "TorrentStateEnum",
    "TransitionNotAllowed",
]
