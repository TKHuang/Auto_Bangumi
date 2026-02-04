"""Mikan anime site HTML parser.

Extracts anime metadata from Mikan search results and bangumi detail pages.
"""

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """Single search result from Mikan search page."""

    mikan_id: str
    title: str
    year: Optional[str] = None
    poster_url: Optional[str] = None


class MikanBangumiInfo(BaseModel):
    """Bangumi detail information from Mikan detail page."""

    mikan_id: str
    title: str
    year: Optional[str] = None
    rss_url: str
    poster_url: Optional[str] = None


def parse_search_results(html: str, base_url: str = "https://mikanani.me") -> list[SearchResult]:
    """Parse Mikan search results page HTML.

    Args:
        html: HTML content of search results page
        base_url: Base URL of Mikan site (default: https://mikanani.me)

    Returns:
        List of SearchResult objects
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    bangumi_links = soup.find_all("a", href=re.compile(r"/Home/Bangumi/\d+"))

    seen_ids = set()
    for link in bangumi_links:
        href = str(link.get("href", ""))
        match = re.search(r"/Home/Bangumi/(\d+)", href)
        if not match:
            continue

        mikan_id = match.group(1)
        if mikan_id in seen_ids:
            continue
        seen_ids.add(mikan_id)

        title = link.get_text(strip=True)
        if not title:
            continue

        poster_url = None
        parent = link.find_parent("li") or link.find_parent("div")
        if parent:
            img = parent.find("img")
            if img:
                src = img.get("src") or img.get("data-src")
                if src:
                    poster_url = str(src)
                    if poster_url.startswith("/"):
                        poster_url = f"{base_url}{poster_url}"

        year = _extract_year(title)

        results.append(
            SearchResult(
                mikan_id=mikan_id,
                title=title,
                year=year,
                poster_url=poster_url,
            )
        )

    return results


def parse_bangumi_page(html: str, base_url: str = "https://mikanani.me") -> MikanBangumiInfo:
    """Parse Mikan bangumi detail page HTML.

    Args:
        html: HTML content of bangumi detail page
        base_url: Base URL of Mikan site (default: https://mikanani.me)

    Returns:
        MikanBangumiInfo object

    Raises:
        ValueError: If required fields cannot be extracted
    """
    soup = BeautifulSoup(html, "html.parser")

    mikan_id = _extract_bangumi_id(soup)
    if not mikan_id:
        raise ValueError("Could not extract mikan_id from bangumi page")

    title = ""
    title_elem = soup.select_one('p.bangumi-title a[href^="/Home/Bangumi/"]')
    if title_elem:
        title = title_elem.text.strip()

    if not title:
        title_elem = soup.find("h1") or soup.find("h2")
        if title_elem:
            title = title_elem.text.strip()

    if not title:
        raise ValueError("Could not extract title from bangumi page")

    poster_url = None
    poster_div = soup.find("div", {"class": "bangumi-poster"})
    if poster_div:
        style = str(poster_div.get("style", ""))
        if "url('" in style:
            poster_path = style.split("url('")[1].split("')")[0]
            poster_path = poster_path.split("?")[0]
            if poster_path.startswith("/"):
                poster_url = f"{base_url}{poster_path}"
            else:
                poster_url = poster_path

    rss_url = _extract_rss_url(soup, base_url)
    if not rss_url:
        raise ValueError("Could not extract RSS URL from bangumi page")

    year = _extract_year(title)

    return MikanBangumiInfo(
        mikan_id=mikan_id,
        title=title,
        year=year,
        rss_url=rss_url,
        poster_url=poster_url,
    )


def _extract_bangumi_id(soup: BeautifulSoup) -> Optional[str]:
    bangumi_link = soup.select_one('a[href^="/Home/Bangumi/"]')
    if bangumi_link:
        href = str(bangumi_link.get("href", ""))
        match = re.search(r"/Home/Bangumi/(\d+)", href)
        if match:
            return match.group(1)

    rss_link = soup.select_one('a[href*="bangumiId"]')
    if rss_link:
        href = str(rss_link.get("href", ""))
        match = re.search(r"bangumiId=(\d+)", href)
        if match:
            return match.group(1)

    return None


def _extract_rss_url(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    rss_link = soup.select_one('a[href*="/RSS/Bangumi"][href*="bangumiId"]')
    if rss_link:
        href = str(rss_link.get("href", ""))
        if href.startswith("/"):
            return f"{base_url}{href}"
        return href

    subscribe_btn = soup.select_one('a[href*="subgroupid"]')
    if subscribe_btn:
        href = str(subscribe_btn.get("href", ""))
        if "RSS/Bangumi" in href or "bangumiId" in href:
            if href.startswith("/"):
                return f"{base_url}{href}"
            return href

    bangumi_id = None
    subgroup_id = None

    bangumi_link = soup.select_one('a[href^="/Home/Bangumi/"]')
    if bangumi_link:
        href = str(bangumi_link.get("href", ""))
        match = re.search(r"/Home/Bangumi/(\d+)", href)
        if match:
            bangumi_id = match.group(1)

    subgroup_link = soup.select_one('a[href*="subgroupid="]')
    if subgroup_link:
        href = str(subgroup_link.get("href", ""))
        match = re.search(r"subgroupid=(\d+)", href)
        if match:
            subgroup_id = match.group(1)

    if bangumi_id and subgroup_id:
        return f"{base_url}/RSS/Bangumi?bangumiId={bangumi_id}&subgroupid={subgroup_id}"

    all_rss_links = soup.find_all("a", href=re.compile(r"RSS"))
    for link in all_rss_links:
        href = str(link.get("href", ""))
        if "Bangumi" in href:
            if href.startswith("/"):
                return f"{base_url}{href}"
            return href

    logger.debug("Could not extract RSS URL from Mikan page")
    return None


def _extract_year(text: str) -> Optional[str]:
    match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
    if match:
        return match.group(1)
    return None
