"""Tests for the Renamer module, especially gen_path method."""

import pytest

from module.manager.renamer import Renamer
from module.models.torrent import EpisodeFile, SubtitleFile


class TestGenPathMovieHandling:
    """Test gen_path method for movie handling."""

    def test_movie_pn_method(self):
        """Test movie renaming with pn method."""
        file_info = EpisodeFile(
            media_path="/downloads/[Group][Movie_Title][MOVIE][1080P].mp4",
            group="Group",
            title="Movie Title",
            season=1,
            episode=None,
            suffix=".mp4",
            is_movie=True,
        )
        result = Renamer.gen_path(file_info, "Official Title", "pn")
        assert result == "Movie Title.mp4"

    def test_movie_advance_method(self):
        """Test movie renaming with advance method."""
        file_info = EpisodeFile(
            media_path="/downloads/[Group][Movie_Title][MOVIE][1080P].mp4",
            group="Group",
            title="Movie Title",
            season=1,
            episode=None,
            suffix=".mp4",
            is_movie=True,
        )
        result = Renamer.gen_path(file_info, "Official Title", "advance")
        assert result == "Official Title.mp4"

    def test_movie_none_method(self):
        """Test movie with none method returns original path."""
        file_info = EpisodeFile(
            media_path="/downloads/[Group][Movie_Title][MOVIE][1080P].mp4",
            group="Group",
            title="Movie Title",
            season=1,
            episode=None,
            suffix=".mp4",
            is_movie=True,
        )
        result = Renamer.gen_path(file_info, "Official Title", "none")
        assert result == "/downloads/[Group][Movie_Title][MOVIE][1080P].mp4"

    def test_movie_subtitle_pn_method(self):
        """Test movie subtitle renaming with subtitle_pn method."""
        file_info = SubtitleFile(
            media_path="/downloads/[Group][Movie_Title][MOVIE].zh.srt",
            group="Group",
            title="Movie Title",
            season=1,
            episode=None,
            language="zh",
            suffix=".srt",
            is_movie=True,
        )
        result = Renamer.gen_path(file_info, "Official Title", "subtitle_pn")
        assert result == "Movie Title.zh.srt"

    def test_movie_subtitle_advance_method(self):
        """Test movie subtitle renaming with subtitle_advance method."""
        file_info = SubtitleFile(
            media_path="/downloads/[Group][Movie_Title][MOVIE].zh.srt",
            group="Group",
            title="Movie Title",
            season=1,
            episode=None,
            language="zh",
            suffix=".srt",
            is_movie=True,
        )
        result = Renamer.gen_path(file_info, "Official Title", "subtitle_advance")
        assert result == "Official Title.zh.srt"

    def test_chainsaw_man_movie(self):
        """Test real-world Chainsaw Man movie case."""
        file_info = EpisodeFile(
            media_path="[BeanSub&FZSD][Chainsaw_Man_Reze_Arc][MOVIE][GB][1080P][x264_AAC].mp4",
            group="BeanSub&FZSD",
            title="Chainsaw Man Reze Arc",
            season=1,
            episode=None,
            suffix=".mp4",
            is_movie=True,
        )
        result = Renamer.gen_path(file_info, "链锯人 蕾塞篇", "advance")
        assert result == "链锯人 蕾塞篇.mp4"


class TestGenPathEpisodeHandling:
    """Test gen_path method for regular episode handling."""

    def test_episode_pn_method(self):
        """Test regular episode renaming with pn method."""
        file_info = EpisodeFile(
            media_path="/downloads/[Group] Title - 01 [1080P].mp4",
            group="Group",
            title="Title",
            season=1,
            episode=1,
            suffix=".mp4",
            is_movie=False,
        )
        result = Renamer.gen_path(file_info, "Official Title", "pn")
        assert result == "Title S01E01.mp4"

    def test_episode_advance_method(self):
        """Test regular episode renaming with advance method."""
        file_info = EpisodeFile(
            media_path="/downloads/[Group] Title - 01 [1080P].mp4",
            group="Group",
            title="Title",
            season=1,
            episode=1,
            suffix=".mp4",
            is_movie=False,
        )
        result = Renamer.gen_path(file_info, "Official Title", "advance")
        assert result == "Official Title S01E01.mp4"

    def test_episode_two_digit_season(self):
        """Test episode with two-digit season."""
        file_info = EpisodeFile(
            media_path="/downloads/[Group] Title - 01 [1080P].mp4",
            group="Group",
            title="Title",
            season=12,
            episode=5,
            suffix=".mp4",
            is_movie=False,
        )
        result = Renamer.gen_path(file_info, "Official Title", "pn")
        assert result == "Title S12E05.mp4"

    def test_episode_two_digit_episode(self):
        """Test episode with two-digit episode number."""
        file_info = EpisodeFile(
            media_path="/downloads/[Group] Title - 15 [1080P].mp4",
            group="Group",
            title="Title",
            season=1,
            episode=15,
            suffix=".mp4",
            is_movie=False,
        )
        result = Renamer.gen_path(file_info, "Official Title", "pn")
        assert result == "Title S01E15.mp4"

    def test_episode_none_returns_original_path(self):
        """Test that episode=None for non-movie returns original path."""
        file_info = EpisodeFile(
            media_path="/downloads/[Group] Title [1080P].mp4",
            group="Group",
            title="Title",
            season=1,
            episode=None,
            suffix=".mp4",
            is_movie=False,
        )
        result = Renamer.gen_path(file_info, "Official Title", "pn")
        assert result == "/downloads/[Group] Title [1080P].mp4"

    def test_episode_decimal_converts_to_int(self):
        """Test that decimal episodes like 5.0 become 5."""
        file_info = EpisodeFile(
            media_path="/downloads/[Group] Title - 05 [1080P].mp4",
            group="Group",
            title="Title",
            season=1,
            episode=5.0,
            suffix=".mp4",
            is_movie=False,
        )
        result = Renamer.gen_path(file_info, "Official Title", "pn")
        assert result == "Title S01E05.mp4"

    def test_episode_decimal_preserved(self):
        """Test that non-whole decimal episodes are preserved."""
        file_info = EpisodeFile(
            media_path="/downloads/[Group] Title - 05.5 [1080P].mp4",
            group="Group",
            title="Title",
            season=1,
            episode=5.5,
            suffix=".mp4",
            is_movie=False,
        )
        result = Renamer.gen_path(file_info, "Official Title", "pn")
        assert result == "Title S01E05.5.mp4"


class TestGenPathSubtitleHandling:
    """Test gen_path method for subtitle handling."""

    def test_subtitle_pn_method(self):
        """Test subtitle renaming with subtitle_pn method."""
        file_info = SubtitleFile(
            media_path="/downloads/[Group] Title - 01.zh.srt",
            group="Group",
            title="Title",
            season=1,
            episode=1,
            language="zh",
            suffix=".srt",
            is_movie=False,
        )
        result = Renamer.gen_path(file_info, "Official Title", "subtitle_pn")
        assert result == "Title S01E01.zh.srt"

    def test_subtitle_advance_method(self):
        """Test subtitle renaming with subtitle_advance method."""
        file_info = SubtitleFile(
            media_path="/downloads/[Group] Title - 01.zh.srt",
            group="Group",
            title="Title",
            season=1,
            episode=1,
            language="zh",
            suffix=".srt",
            is_movie=False,
        )
        result = Renamer.gen_path(file_info, "Official Title", "subtitle_advance")
        assert result == "Official Title S01E01.zh.srt"

    def test_subtitle_none_method(self):
        """Test subtitle with subtitle_none method returns original path."""
        file_info = SubtitleFile(
            media_path="/downloads/[Group] Title - 01.zh.srt",
            group="Group",
            title="Title",
            season=1,
            episode=1,
            language="zh",
            suffix=".srt",
            is_movie=False,
        )
        result = Renamer.gen_path(file_info, "Official Title", "subtitle_none")
        assert result == "/downloads/[Group] Title - 01.zh.srt"

    def test_subtitle_zh_tw_language(self):
        """Test subtitle with zh-tw language."""
        file_info = SubtitleFile(
            media_path="/downloads/[Group] Title - 01.zh-tw.srt",
            group="Group",
            title="Title",
            season=1,
            episode=1,
            language="zh-tw",
            suffix=".srt",
            is_movie=False,
        )
        result = Renamer.gen_path(file_info, "Official Title", "subtitle_pn")
        assert result == "Title S01E01.zh-tw.srt"
