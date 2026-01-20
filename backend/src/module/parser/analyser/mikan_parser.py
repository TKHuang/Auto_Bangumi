import logging
import re
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup
from urllib3.util import parse_url

from module.network import RequestContent
from module.utils import save_image

logger = logging.getLogger(__name__)


@dataclass
class MikanParserResult:
    """Result from parsing a Mikan episode page."""

    poster_link: str
    official_title: str
    season_rss_link: Optional[str] = None


def mikan_parser(homepage: str) -> tuple[str, str]:
    """Parse Mikan episode page for poster and title.

    Args:
        homepage: URL of the Mikan episode page.

    Returns:
        Tuple of (poster_link, official_title).
    """
    result = mikan_parser_with_rss(homepage)
    return result.poster_link, result.official_title


def mikan_parser_with_rss(homepage: str) -> MikanParserResult:
    """Parse Mikan episode page for poster, title, and season RSS link.

    Args:
        homepage: URL of the Mikan episode page (e.g., /Home/Episode/xxx).

    Returns:
        MikanParserResult containing poster_link, official_title, and season_rss_link.
    """
    parsed_url = parse_url(homepage)
    root_path = parsed_url.host
    scheme = parsed_url.scheme or "https"
    base_url = f"{scheme}://{root_path}"

    with RequestContent() as req:
        content = req.get_html(homepage)
        soup = BeautifulSoup(content, "html.parser")

        # Extract poster
        poster_link = ""
        poster_div = soup.find("div", {"class": "bangumi-poster"})
        if poster_div:
            style = poster_div.get("style", "")
            if "url('" in style:
                poster_path = style.split("url('")[1].split("')")[0]
                poster_path = poster_path.split("?")[0]
                img = req.get_content(f"{base_url}{poster_path}")
                suffix = poster_path.split(".")[-1]
                poster_link = save_image(img, suffix)

        # Extract official title
        official_title = ""
        title_elem = soup.select_one('p.bangumi-title a[href^="/Home/Bangumi/"]')
        if title_elem:
            official_title = title_elem.text
            official_title = re.sub(r"第.*季", "", official_title).strip()

        # Extract season-specific RSS link
        # Look for RSS link with bangumiId and subgroupid parameters
        season_rss_link = _extract_season_rss_link(soup, base_url)

        return MikanParserResult(
            poster_link=poster_link,
            official_title=official_title,
            season_rss_link=season_rss_link,
        )


def _extract_season_rss_link(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    """Extract season-specific RSS link from the episode page.

    Args:
        soup: BeautifulSoup object of the episode page.
        base_url: Base URL of the Mikan site (e.g., https://mikanani.me).

    Returns:
        Full RSS URL with bangumiId and subgroupid, or None if not found.
    """
    # Method 1: Look for direct RSS link with bangumiId and subgroupid
    rss_link = soup.select_one('a[href*="/RSS/Bangumi"][href*="bangumiId"]')
    if rss_link:
        href = rss_link.get("href", "")
        if href.startswith("/"):
            return f"{base_url}{href}"
        return href

    # Method 2: Extract from data attributes or JavaScript
    # Look for subscription button or RSS feed link
    subscribe_btn = soup.select_one('a[href*="subgroupid"]')
    if subscribe_btn:
        href = subscribe_btn.get("href", "")
        if "RSS/Bangumi" in href or "bangumiId" in href:
            if href.startswith("/"):
                return f"{base_url}{href}"
            return href

    # Method 3: Build from page elements
    # Extract bangumiId from the bangumi link
    bangumi_link = soup.select_one('a[href^="/Home/Bangumi/"]')
    subgroup_link = soup.select_one('a[href*="subgroupid="]')

    if bangumi_link and subgroup_link:
        bangumi_href = bangumi_link.get("href", "")
        subgroup_href = subgroup_link.get("href", "")

        # Extract bangumiId from /Home/Bangumi/xxxx
        bangumi_match = re.search(r"/Home/Bangumi/(\d+)", bangumi_href)
        # Extract subgroupid from href containing subgroupid=xx
        subgroup_match = re.search(r"subgroupid=(\d+)", subgroup_href)

        if bangumi_match and subgroup_match:
            bangumi_id = bangumi_match.group(1)
            subgroup_id = subgroup_match.group(1)
            return f"{base_url}/RSS/Bangumi?bangumiId={bangumi_id}&subgroupid={subgroup_id}"

    # Method 4: Try to find bangumiId from any element and subgroupid from subgroup section
    bangumi_id = None
    subgroup_id = None

    # Find bangumiId from any bangumi-related link
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if "/Home/Bangumi/" in href:
            match = re.search(r"/Home/Bangumi/(\d+)", href)
            if match:
                bangumi_id = match.group(1)
                break

    # Find subgroupid from subgroup-related elements
    subgroup_elem = soup.select_one(".magnet-link-wrap .subgroup-text")
    if subgroup_elem:
        parent_link = subgroup_elem.find_parent("a")
        if parent_link:
            href = parent_link.get("href", "")
            match = re.search(r"subgroupid=(\d+)", href)
            if match:
                subgroup_id = match.group(1)

    # Also check for subgroup links in the episode info area
    if not subgroup_id:
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            match = re.search(r"subgroupid=(\d+)", href)
            if match:
                subgroup_id = match.group(1)
                break

    if bangumi_id and subgroup_id:
        return f"{base_url}/RSS/Bangumi?bangumiId={bangumi_id}&subgroupid={subgroup_id}"

    logger.debug("[Parser] Could not extract season RSS link from Mikan page")
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    homepage = "https://mikanani.me/Home/Episode/c89b3c6f0c1c0567a618f5288b853823c87a9862"
    result = mikan_parser_with_rss(homepage)
    logger.info(f"Poster: {result.poster_link}")
    logger.info(f"Title: {result.official_title}")
    logger.info(f"Season RSS: {result.season_rss_link}")
