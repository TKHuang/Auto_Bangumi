import logging
from dataclasses import dataclass
from typing import Optional

from urllib3.util import parse_url

from module.conf import settings
from module.mikan.parser import (
    build_season_rss_url,
    parse_mikan_page,
    parse_mikan_title_and_poster,
)
from module.models import Bangumi
from module.network import RequestContent
from module.utils import save_image
from module.domain.value_objects import BangumiParsingError, Episode
from module.domain.parser.analyser import (
    OpenAIParser,
    raw_parser,
    tmdb_parser,
    torrent_parser,
)

logger = logging.getLogger(__name__)


@dataclass
class MikanParserResult:
    """Result from parsing a Mikan episode page."""

    poster_link: str
    official_title: str
    season_rss_link: Optional[str] = None


class TitleParser:
    def __init__(self):
        pass

    @staticmethod
    def torrent_parser(
        torrent_path: str,
        torrent_name: str | None = None,
        season: int | None = None,
        file_type: str = "media",
    ):
        try:
            return torrent_parser(torrent_path, torrent_name, season, file_type)
        except Exception as e:
            logger.warning(f"Cannot parse {torrent_path} with error {e}")

    @staticmethod
    def tmdb_parser(title: str, season: int, language: str):
        tmdb_info = tmdb_parser(title, language)
        if tmdb_info:
            logger.debug(f"TMDB Matched, official title is {tmdb_info.title}")
            tmdb_season = tmdb_info.last_season if tmdb_info.last_season else season
            return tmdb_info.title, tmdb_season, tmdb_info.year, tmdb_info.poster_link
        else:
            logger.warning(f"Cannot match {title} in TMDB. Use raw title instead.")
            logger.warning("Please change bangumi info manually.")
            return title, season, None, None

    @staticmethod
    def tmdb_poster_parser(bangumi: Bangumi):
        tmdb_info = tmdb_parser(bangumi.official_title, settings.rss_parser.language)
        if tmdb_info:
            logger.debug(f"TMDB Matched, official title is {tmdb_info.title}")
            bangumi.poster_link = tmdb_info.poster_link
        else:
            logger.warning(
                f"Cannot match {bangumi.official_title} in TMDB. Use raw title instead."
            )
            logger.warning("Please change bangumi info manually.")

    @staticmethod
    def raw_parser(raw: str) -> Bangumi | None:
        language = settings.rss_parser.language
        try:
            # use OpenAI ChatGPT to parse raw title and get structured data
            if settings.experimental_openai.enable:
                kwargs = settings.experimental_openai.dict(exclude={"enable"})
                gpt = OpenAIParser(**kwargs)
                episode_dict = gpt.parse(raw, asdict=True)
                episode = Episode(**episode_dict)
            else:
                logger.debug(f"Using raw parser to parse {raw}")
                episode = raw_parser(raw)
                logger.debug(f"Raw parser result: {episode}")

            titles = {
                "zh": episode.title_zh,
                "en": episode.title_en,
                "jp": episode.title_jp,
            }
            title_raw = episode.title_en if episode.title_en else episode.title_zh
            if titles[language]:
                official_title = titles[language]
            elif titles["zh"]:
                official_title = titles["zh"]
            elif titles["en"]:
                official_title = titles["en"]
            elif titles["jp"]:
                official_title = titles["jp"]
            else:
                official_title = title_raw
            _season = episode.season
            logger.debug(f"RAW:{raw} >> {title_raw}")
            return Bangumi(
                official_title=official_title,
                title_raw=title_raw,
                season=_season,
                season_raw=episode.season_raw,
                group_name=episode.group,
                dpi=episode.resolution,
                source=episode.source,
                subtitle=episode.sub,
                eps_collect=False if episode.episode > 1 else True,
                offset=0,
                filter=",".join(settings.rss_parser.filter),
            )
        except BangumiParsingError:
            # Re-raise BangumiParsingError to allow caller to handle it
            raise
        except Exception as e:
            logger.debug(e)
            logger.warning(f"Cannot parse {raw}.")
            return None

    @staticmethod
    def mikan_parser_with_rss(homepage: str) -> MikanParserResult:
        """Fetch a Mikan episode page; return poster, title and season RSS link.

        The poster is downloaded and cached; ``poster_link`` is its local path.
        Never raises on an unknown page: missing parts come back empty.
        """
        parsed_url = parse_url(homepage)
        base_url = f"{parsed_url.scheme or 'https'}://{parsed_url.host}"

        with RequestContent() as req:
            html = req.get_html(homepage)
            title, poster_path = parse_mikan_title_and_poster(html)

            poster_link = ""
            if poster_path:
                poster_path = poster_path.split("?")[0]
                img = req.get_content(f"{base_url}{poster_path}")
                poster_link = save_image(img, poster_path.split(".")[-1])

        season_rss_link = None
        ref = parse_mikan_page(html)
        if ref and ref.mikan_bangumi_id > 0 and ref.mikan_subgroup_id > 0:
            season_rss_link = build_season_rss_url(
                ref.mikan_bangumi_id, ref.mikan_subgroup_id, base_url=base_url
            )

        return MikanParserResult(
            poster_link=poster_link,
            official_title=title or "",
            season_rss_link=season_rss_link,
        )
