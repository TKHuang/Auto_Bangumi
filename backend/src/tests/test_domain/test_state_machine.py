"""Tests for torrent state machine."""

import pytest
from statemachine.exceptions import TransitionNotAllowed

from module.domain.state_machine import (
    TorrentStateEnum,
    TorrentStateMachine,
)


class TestTorrentStateMachine:
    """Test suite for TorrentStateMachine."""

    def test_initial_state_is_pending(self):
        sm = TorrentStateMachine()
        assert sm.current_state.id == TorrentStateEnum.PENDING

    def test_queue_transition_pending_to_queued(self):
        sm = TorrentStateMachine()
        sm.queue()
        assert sm.current_state.id == TorrentStateEnum.QUEUED

    def test_start_download_transition_queued_to_downloading(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()
        assert sm.current_state.id == TorrentStateEnum.DOWNLOADING

    def test_complete_transition_downloading_to_completed(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()
        sm.complete()
        assert sm.current_state.id == TorrentStateEnum.COMPLETED

    def test_start_rename_transition_completed_to_renaming(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()
        sm.complete()
        sm.start_rename()
        assert sm.current_state.id == TorrentStateEnum.RENAMING

    def test_finish_rename_transition_renaming_to_renamed(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()
        sm.complete()
        sm.start_rename()
        sm.finish_rename()
        assert sm.current_state.id == TorrentStateEnum.RENAMED

    def test_happy_path_full_lifecycle(self):
        sm = TorrentStateMachine()
        assert sm.current_state.id == TorrentStateEnum.PENDING

        sm.queue()
        assert sm.current_state.id == TorrentStateEnum.QUEUED

        sm.start_download()
        assert sm.current_state.id == TorrentStateEnum.DOWNLOADING

        sm.complete()
        assert sm.current_state.id == TorrentStateEnum.COMPLETED

        sm.start_rename()
        assert sm.current_state.id == TorrentStateEnum.RENAMING

        sm.finish_rename()
        assert sm.current_state.id == TorrentStateEnum.RENAMED

    def test_fail_from_pending_to_error(self):
        sm = TorrentStateMachine()
        sm.fail()
        assert sm.current_state.id == TorrentStateEnum.ERROR

    def test_fail_from_queued_to_error(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.fail()
        assert sm.current_state.id == TorrentStateEnum.ERROR

    def test_fail_from_downloading_to_error(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()
        sm.fail()
        assert sm.current_state.id == TorrentStateEnum.ERROR

    def test_fail_from_renaming_to_error(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()
        sm.complete()
        sm.start_rename()
        sm.fail()
        assert sm.current_state.id == TorrentStateEnum.ERROR

    def test_mark_stale_transition_completed_to_stale(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()
        sm.complete()
        sm.mark_stale()
        assert sm.current_state.id == TorrentStateEnum.STALE

    def test_recover_transition_stale_to_completed(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()
        sm.complete()
        sm.mark_stale()
        sm.recover()
        assert sm.current_state.id == TorrentStateEnum.COMPLETED

    def test_recovery_path_stale_to_completed(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()
        sm.complete()
        assert sm.current_state.id == TorrentStateEnum.COMPLETED

        sm.mark_stale()
        assert sm.current_state.id == TorrentStateEnum.STALE

        sm.recover()
        assert sm.current_state.id == TorrentStateEnum.COMPLETED

    def test_mark_missing_from_completed(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()
        sm.complete()
        sm.mark_missing()
        assert sm.current_state.id == TorrentStateEnum.MISSING

    def test_mark_missing_from_stale(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()
        sm.complete()
        sm.mark_stale()
        sm.mark_missing()
        assert sm.current_state.id == TorrentStateEnum.MISSING

    def test_missing_after_failed_recovery(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()
        sm.complete()
        sm.mark_stale()
        assert sm.current_state.id == TorrentStateEnum.STALE

        sm.mark_missing()
        assert sm.current_state.id == TorrentStateEnum.MISSING

    def test_retry_transition_error_to_pending(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.fail()
        assert sm.current_state.id == TorrentStateEnum.ERROR

        sm.retry()
        assert sm.current_state.id == TorrentStateEnum.PENDING

    def test_retry_path_error_to_pending(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()
        sm.fail()
        assert sm.current_state.id == TorrentStateEnum.ERROR

        sm.retry()
        assert sm.current_state.id == TorrentStateEnum.PENDING

        sm.queue()
        sm.start_download()
        sm.complete()
        assert sm.current_state.id == TorrentStateEnum.COMPLETED

    def test_invalid_transition_queue_from_downloading_raises_error(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()

        with pytest.raises(TransitionNotAllowed):
            sm.queue()

    def test_invalid_transition_start_download_from_pending_raises_error(self):
        sm = TorrentStateMachine()

        with pytest.raises(TransitionNotAllowed):
            sm.start_download()

    def test_invalid_transition_complete_from_pending_raises_error(self):
        sm = TorrentStateMachine()

        with pytest.raises(TransitionNotAllowed):
            sm.complete()

    def test_invalid_transition_start_rename_from_downloading_raises_error(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()

        with pytest.raises(TransitionNotAllowed):
            sm.start_rename()

    def test_invalid_transition_finish_rename_from_completed_raises_error(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()
        sm.complete()

        with pytest.raises(TransitionNotAllowed):
            sm.finish_rename()

    def test_invalid_transition_fail_from_completed_raises_error(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()
        sm.complete()

        with pytest.raises(TransitionNotAllowed):
            sm.fail()

    def test_invalid_transition_fail_from_renamed_raises_error(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()
        sm.complete()
        sm.start_rename()
        sm.finish_rename()

        with pytest.raises(TransitionNotAllowed):
            sm.fail()

    def test_invalid_transition_mark_stale_from_pending_raises_error(self):
        sm = TorrentStateMachine()

        with pytest.raises(TransitionNotAllowed):
            sm.mark_stale()

    def test_invalid_transition_recover_from_completed_raises_error(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()
        sm.complete()

        with pytest.raises(TransitionNotAllowed):
            sm.recover()

    def test_invalid_transition_mark_missing_from_pending_raises_error(self):
        sm = TorrentStateMachine()

        with pytest.raises(TransitionNotAllowed):
            sm.mark_missing()

    def test_invalid_transition_retry_from_pending_raises_error(self):
        sm = TorrentStateMachine()

        with pytest.raises(TransitionNotAllowed):
            sm.retry()

    def test_invalid_transition_retry_from_completed_raises_error(self):
        sm = TorrentStateMachine()
        sm.queue()
        sm.start_download()
        sm.complete()

        with pytest.raises(TransitionNotAllowed):
            sm.retry()


class TestTorrentStateMachineFromStr:
    """Test suite for TorrentStateMachine.from_str() deserialization."""

    @pytest.mark.parametrize(
        "state_string,expected_state",
        [
            ("pending", TorrentStateEnum.PENDING),
            ("queued", TorrentStateEnum.QUEUED),
            ("downloading", TorrentStateEnum.DOWNLOADING),
            ("completed", TorrentStateEnum.COMPLETED),
            ("renaming", TorrentStateEnum.RENAMING),
            ("renamed", TorrentStateEnum.RENAMED),
            ("error", TorrentStateEnum.ERROR),
            ("stale", TorrentStateEnum.STALE),
            ("missing", TorrentStateEnum.MISSING),
        ],
    )
    def test_from_str_creates_correct_state(self, state_string, expected_state):
        sm = TorrentStateMachine.from_str(state_string)
        assert sm.current_state.id == expected_state

    @pytest.mark.parametrize(
        "state_string",
        [
            "PENDING",
            "Queued",
            "DOWNLOADING",
            "CoMpLeTeD",
        ],
    )
    def test_from_str_case_insensitive(self, state_string):
        sm = TorrentStateMachine.from_str(state_string)
        assert sm.current_state.id == state_string.lower()

    def test_from_str_invalid_state_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid state 'invalid'"):
            TorrentStateMachine.from_str("invalid")

    def test_from_str_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            TorrentStateMachine.from_str("")

    def test_from_str_completed_can_transition_to_renaming(self):
        sm = TorrentStateMachine.from_str("completed")
        sm.start_rename()
        assert sm.current_state.id == TorrentStateEnum.RENAMING

    def test_from_str_error_can_retry(self):
        sm = TorrentStateMachine.from_str("error")
        sm.retry()
        assert sm.current_state.id == TorrentStateEnum.PENDING

    def test_from_str_stale_can_recover(self):
        sm = TorrentStateMachine.from_str("stale")
        sm.recover()
        assert sm.current_state.id == TorrentStateEnum.COMPLETED

    def test_from_str_completed_can_mark_stale(self):
        sm = TorrentStateMachine.from_str("completed")
        sm.mark_stale()
        assert sm.current_state.id == TorrentStateEnum.STALE

    def test_from_str_stale_can_mark_missing(self):
        sm = TorrentStateMachine.from_str("stale")
        sm.mark_missing()
        assert sm.current_state.id == TorrentStateEnum.MISSING


class TestTorrentStateMachineCallbacks:
    """Test suite for state entry callbacks."""

    def test_on_enter_state_callback_exists(self):
        sm = TorrentStateMachine()
        assert hasattr(sm, "on_enter_state")
        assert callable(sm.on_enter_state)

    def test_on_enter_state_can_be_overridden(self):
        called = []

        class TrackedStateMachine(TorrentStateMachine):
            def on_enter_state(self, target, source):
                called.append((source.id, target.id))

        sm = TrackedStateMachine()
        sm.queue()

        assert (TorrentStateEnum.PENDING, TorrentStateEnum.QUEUED) in called

    def test_on_enter_state_tracks_all_transitions(self):
        transitions = []

        class TrackedStateMachine(TorrentStateMachine):
            def on_enter_state(self, target, source):
                transitions.append(target.id)

        sm = TrackedStateMachine()
        sm.queue()
        sm.start_download()
        sm.complete()
        sm.start_rename()
        sm.finish_rename()

        assert TorrentStateEnum.QUEUED in transitions
        assert TorrentStateEnum.DOWNLOADING in transitions
        assert TorrentStateEnum.COMPLETED in transitions
        assert TorrentStateEnum.RENAMING in transitions
        assert TorrentStateEnum.RENAMED in transitions
