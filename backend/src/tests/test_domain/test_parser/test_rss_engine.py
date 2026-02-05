from module.rss.engine import RSSEngine

from .test_database import engine as e


def test_rss_engine():
    with RSSEngine(e) as engine:
        rss_link = "https://mikanani.me/RSS/Bangumi?bangumiId=2353&subgroupid=552"

        engine.add_rss(rss_link, aggregate=False)
        engine.commit()

        result = engine.rss.search_active()
        assert len(result) > 0, "No RSS items found after adding RSS"
        # Find the added RSS by matching the URL
        added_rss = None
        for rss in result:
            if rss.url == rss_link:
                added_rss = rss
                break
        assert added_rss is not None, f"Added RSS with URL {rss_link} not found"
        assert added_rss.name == "无职转生～到了异世界就拿出真本事～"

        new_torrents = engine.pull_rss(added_rss)
        torrent = new_torrents[0]
        assert (
            torrent.name
            == "[Lilith-Raws] 无职转生，到了异世界就拿出真本事 / Mushoku Tensei - 11 [Baha][WEB-DL][1080p][AVC AAC][CHT][MP4]"
        )
