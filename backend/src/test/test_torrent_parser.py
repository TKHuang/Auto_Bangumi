import sys

import pytest

from module.parser.analyser import torrent_parser
from module.parser.analyser.torrent_parser import get_path_basename


def test_torrent_parser():
    file_name = "[Lilith-Raws] Boku no Kokoro no Yabai Yatsu - 01 [Baha][WEB-DL][1080p][AVC AAC][CHT][MP4].mp4"
    bf = torrent_parser(file_name)
    assert bf.title == "Boku no Kokoro no Yabai Yatsu"
    assert bf.group == "Lilith-Raws"
    assert bf.episode == 1
    assert bf.season == 1

    file_name = "[Sakurato] Tonikaku Kawaii S2 [01][AVC-8bit 1080p AAC][CHS].mp4"
    bf = torrent_parser(file_name)
    assert bf.title == "Tonikaku Kawaii"
    assert bf.group == "Sakurato"
    assert bf.episode == 1
    assert bf.season == 2

    file_name = "[SweetSub&LoliHouse] Heavenly Delusion - 01 [WebRip 1080p HEVC-10bit AAC ASSx2].mkv"
    bf = torrent_parser(file_name)
    assert bf.title == "Heavenly Delusion"
    assert bf.group == "SweetSub&LoliHouse"
    assert bf.episode == 1
    assert bf.season == 1

    file_name = "[SBSUB][CONAN][1082][V2][1080P][AVC_AAC][CHS_JP](C1E4E331).mp4"
    bf = torrent_parser(file_name)
    assert bf.title == "CONAN"
    assert bf.group == "SBSUB"
    assert bf.episode == 1082
    assert bf.season == 1

    file_name = "海盗战记 (2019) S01E01.mp4"
    bf = torrent_parser(file_name)
    assert bf.title == "海盗战记 (2019)"
    assert bf.episode == 1
    assert bf.season == 1

    file_name = "海盗战记/海盗战记 S01E01.mp4"
    bf = torrent_parser(file_name)
    assert bf.title == "海盗战记"
    assert bf.episode == 1
    assert bf.season == 1

    file_name = "海盗战记 S01E01.zh-tw.ass"
    sf = torrent_parser(file_name, file_type="subtitle")
    assert sf.title == "海盗战记"
    assert sf.episode == 1
    assert sf.season == 1
    assert sf.language == "zh-tw"

    file_name = "海盗战记 S01E01.SC.ass"
    sf = torrent_parser(file_name, file_type="subtitle")
    assert sf.title == "海盗战记"
    assert sf.season == 1
    assert sf.episode == 1
    assert sf.language == "zh"

    file_name = "水星的魔女(2022) S00E19.mp4"
    bf = torrent_parser(file_name, season=0)
    assert bf.title == "水星的魔女(2022)"
    assert bf.season == 0
    assert bf.episode == 19

    file_name = "【失眠搬运组】放学后失眠的你-Kimi wa Houkago Insomnia - 06 [bilibili - 1080p AVC1 CHS-JP].mp4"
    bf = torrent_parser(file_name, season=1)
    assert bf.title == "放学后失眠的你-Kimi wa Houkago Insomnia"
    assert bf.season == 1
    assert bf.episode == 6

    file_name = "不时用俄语小声说真心话的邻桌艾莉同学 S01E02.mp4"
    bf = torrent_parser(file_name)
    assert bf.title == "不时用俄语小声说真心话的邻桌艾莉同学"
    assert bf.season == 1
    assert bf.episode == 2

    file_name = "[ANi] 關於我轉生變成史萊姆這檔事 第三季 - 48.5 [1080P][Baha][WEB-DL][AAC AVC][CHT].mp4"
    bf = torrent_parser(file_name, season=3)
    assert bf.title == "關於我轉生變成史萊姆這檔事 第三季"
    assert bf.season == 3
    assert bf.episode == 48.5

    file_name = "[ANi] 關於我轉生變成史萊姆這檔事 第三季 - 48.5 [1080P][Baha][WEB-DL][AAC AVC][CHT].srt"
    sf = torrent_parser(file_name, season=3, file_type="subtitle")
    assert sf.title == "關於我轉生變成史萊姆這檔事 第三季"
    assert sf.episode == 48.5
    assert sf.season == 3
    assert sf.language == "zh-tw"


class TestTorrentFilePathParsing:
    """Test comprehensive file path parsing scenarios.

    Tests cover:
    - Standard paths with season folders
    - Decimal episode paths
    - Subtitle file paths with language markers
    - Movie/OVA file paths
    """

    def test_standard_path_with_season_folder(self):
        """Test parsing file from standard season folder structure."""
        file_path = "/downloads/Bangumi/海盗战记/Season 1/海盗战记 S01E01.mp4"
        bf = torrent_parser(file_path)
        assert bf.title == "海盗战记"
        assert bf.season == 1
        assert bf.episode == 1
        assert bf.media_path == file_path
        assert bf.suffix == ".mp4"

    def test_standard_path_season_2(self):
        """Test parsing file from season 2 folder."""
        file_path = "/anime/Tonikaku Kawaii/Season 2/[Sakurato] Tonikaku Kawaii S2 [01][AVC-8bit 1080p AAC][CHS].mp4"
        bf = torrent_parser(file_path)
        assert bf.title == "Tonikaku Kawaii"
        assert bf.season == 2
        assert bf.episode == 1
        assert bf.group == "Sakurato"

    def test_decimal_episode_path(self):
        """Test parsing file with decimal episode number."""
        file_path = "/downloads/Bangumi/关于我转生变成史莱姆这档事 (2018)/Season 3/[ANi] 關於我轉生變成史萊姆這檔事 第三季 - 48.5 [1080P][Baha][WEB-DL][AAC AVC][CHT].mp4"
        bf = torrent_parser(file_path, season=3)
        assert bf.title == "關於我轉生變成史萊姆這檔事 第三季"
        assert bf.season == 3
        assert bf.episode == 48.5
        assert bf.group == "ANi"

    def test_decimal_episode_batch_path(self):
        """Test parsing file with decimal episode in batch folder."""
        file_path = (
            "/anime/OVA/[LoliHouse] Title - 12.5 [WebRip 1080p HEVC-10bit AAC].mkv"
        )
        bf = torrent_parser(file_path)
        assert bf.title == "Title"
        assert bf.episode == 12.5

    def test_subtitle_path_zh_tw_marker(self):
        """Test parsing subtitle file with zh-tw language marker."""
        file_path = "/downloads/Bangumi/海盗战记/Season 1/海盗战记 S01E01.zh-tw.ass"
        sf = torrent_parser(file_path, file_type="subtitle")
        assert sf.title == "海盗战记"
        assert sf.season == 1
        assert sf.episode == 1
        assert sf.language == "zh-tw"
        assert sf.suffix == ".ass"

    def test_subtitle_path_sc_marker(self):
        """Test parsing subtitle file with SC (simplified Chinese) marker."""
        file_path = "/anime/Title/Season 1/海盗战记 S01E01.SC.ass"
        sf = torrent_parser(file_path, file_type="subtitle")
        assert sf.title == "海盗战记"
        assert sf.season == 1
        assert sf.episode == 1
        assert sf.language == "zh"

    def test_subtitle_path_cht_marker(self):
        """Test parsing subtitle file with CHT marker from BangumiParser."""
        file_path = "/anime/Title/Season 1/[ANi] 關於我轉生變成史萊姆這檔事 第三季 - 48.5 [1080P][Baha][WEB-DL][AAC AVC][CHT].srt"
        sf = torrent_parser(file_path, season=3, file_type="subtitle")
        assert sf.title == "關於我轉生變成史萊姆這檔事 第三季"
        assert sf.season == 3
        assert sf.episode == 48.5
        assert sf.language == "zh-tw"
        assert sf.suffix == ".srt"

    def test_subtitle_path_tc_in_filename(self):
        """Test parsing subtitle file with TC in filename."""
        file_path = "/anime/Title/Title S01E05.TC.ass"
        sf = torrent_parser(file_path, file_type="subtitle")
        assert sf.title == "Title"
        assert sf.season == 1
        assert sf.episode == 5
        assert sf.language == "zh-tw"

    def test_subtitle_path_chs_marker(self):
        """Test parsing subtitle file with CHS marker from BangumiParser."""
        file_path = "/anime/Title/[Group] Title - 01 [1080P][CHS].srt"
        sf = torrent_parser(file_path, file_type="subtitle")
        assert sf.title == "Title"
        assert sf.episode == 1
        assert sf.language == "zh"

    def test_movie_path_with_marker(self):
        """Test parsing movie file with 剧场版 marker."""
        file_path = (
            "/movies/[LoliHouse] 葬送的芙莉莲 剧场版 [WebRip 1080p HEVC-10bit AAC].mkv"
        )
        bf = torrent_parser(file_path)
        # When BangumiParser can't parse title, fallback to stem which includes metadata
        assert "葬送的芙莉莲" in bf.title
        assert bf.season == 1  # Default season
        assert bf.group == "LoliHouse"

    def test_ova_path(self):
        """Test parsing OVA file."""
        file_path = "/anime/OVA/[Group] Title OVA [1080p].mkv"
        bf = torrent_parser(file_path)
        assert bf.title == "Title OVA"
        assert bf.season == 1

    def test_special_path(self):
        """Test parsing special episode file with bracketed episode number."""
        file_path = "/anime/Specials/[Group] Title Special [01][1080p].mkv"
        bf = torrent_parser(file_path)
        assert "Title" in bf.title
        assert bf.episode == 1
        assert bf.group == "Group"

    def test_path_with_nested_folders(self):
        """Test parsing file from deeply nested folder structure."""
        file_path = "/media/downloads/anime/2024/不时用俄语小声说真心话的邻桌艾莉同学/Season 1/不时用俄语小声说真心话的邻桌艾莉同学 S01E02.mp4"
        bf = torrent_parser(file_path)
        assert bf.title == "不时用俄语小声说真心话的邻桌艾莉同学"
        assert bf.season == 1
        assert bf.episode == 2

    def test_path_with_year_in_title(self):
        """Test parsing file with year in title."""
        file_path = "/anime/海盗战记/Season 1/海盗战记 (2019) S01E01.mp4"
        bf = torrent_parser(file_path)
        assert bf.title == "海盗战记 (2019)"
        assert bf.season == 1
        assert bf.episode == 1

    def test_path_with_season_0(self):
        """Test parsing file with season 0 (specials)."""
        file_path = "/anime/水星的魔女/Season 0/水星的魔女(2022) S00E19.mp4"
        bf = torrent_parser(file_path, season=0)
        assert bf.title == "水星的魔女(2022)"
        assert bf.season == 0
        assert bf.episode == 19

    def test_path_with_complex_filename(self):
        """Test parsing file with complex fansub format."""
        file_path = "/downloads/【失眠搬运组】放学后失眠的你-Kimi wa Houkago Insomnia/Season 1/【失眠搬运组】放学后失眠的你-Kimi wa Houkago Insomnia - 06 [bilibili - 1080p AVC1 CHS-JP].mp4"
        bf = torrent_parser(file_path, season=1)
        assert bf.title == "放学后失眠的你-Kimi wa Houkago Insomnia"
        assert bf.season == 1
        assert bf.episode == 6

    def test_path_with_mkv_extension(self):
        """Test parsing MKV file."""
        file_path = "/anime/Title/[SweetSub&LoliHouse] Heavenly Delusion - 01 [WebRip 1080p HEVC-10bit AAC ASSx2].mkv"
        bf = torrent_parser(file_path)
        assert bf.title == "Heavenly Delusion"
        assert bf.episode == 1
        assert bf.suffix == ".mkv"

    def test_path_with_multi_group(self):
        """Test parsing file with multiple groups."""
        file_path = "/anime/Title/[SweetSub&LoliHouse] Heavenly Delusion - 01 [WebRip 1080p HEVC-10bit AAC ASSx2].mkv"
        bf = torrent_parser(file_path)
        assert bf.group == "SweetSub&LoliHouse"
        assert bf.title == "Heavenly Delusion"

    def test_path_basename_extraction(self):
        """Test that basename is correctly extracted from path."""
        file_path = "/very/long/path/to/anime/folder/[Group] Title - 01 [1080p].mp4"
        bf = torrent_parser(file_path)
        assert bf.media_path == file_path
        assert bf.title == "Title"
        assert bf.episode == 1
        assert bf.group == "Group"


class TestGetPathBasename:
    def test_regular_path(self):
        assert get_path_basename("/path/to/file.txt") == "file.txt"

    def test_empty_path(self):
        assert get_path_basename("") == ""

    def test_path_with_trailing_slash(self):
        assert get_path_basename("/path/to/folder/") == "folder"

    @pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows specific")
    def test_windows_path(self):
        assert get_path_basename("C:\\path\\to\\file.txt") == "file.txt"
