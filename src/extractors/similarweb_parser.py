import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup  # type: ignore

from extractors.utils_data import (
    normalize_domain,
    safe_float,
    safe_int,
    timestamp_now_iso,
)

logger = logging.getLogger(__name__)

@dataclass
class ScraperConfig:
    base_url: str
    user_agent: str
    timeout: float

class SimilarwebScraper:
    """
    Scrapes public Similarweb pages and extracts traffic and ranking metrics.

    This implementation is intentionally defensive. It attempts multiple strategies:
    - Parsing embedded JSON script tags
    - Looking for labels like "Global Rank" and nearby numbers
    - Falling back to generic HTML/meta extraction for basic info
    """

    def __init__(self, base_url: str, user_agent: str, timeout: float = 15.0) -> None:
        self.config = ScraperConfig(base_url=base_url.rstrip("/"), user_agent=user_agent, timeout=timeout)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.config.user_agent})

    def build_similarweb_url(self, target: str) -> str:
        # If it's already a Similarweb URL, just normalize and return.
        if "similarweb.com" in target:
            return target

        domain = normalize_domain(target)
        url = f"{self.config.base_url}/{domain}"
        logger.debug("Built Similarweb URL '%s' from target '%s'", url, target)
        return url

    def _fetch_page(self, url: str) -> str:
        logger.debug("Fetching URL: %s", url)
        resp = self.session.get(url, timeout=self.config.timeout)
        resp.raise_for_status()
        return resp.text

    def _extract_basic_site_meta(self, soup: BeautifulSoup, similarweb_url: str) -> Dict[str, Any]:
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None

        meta_desc = soup.find("meta", attrs={"name": "description"})
        description = meta_desc.get("content", "").strip() if meta_desc and meta_desc.get("content") else None

        # Use domain of underlying target when we can infer it from URL path.
        parsed = urlparse(similarweb_url)
        path_segments = [p for p in parsed.path.split("/") if p]
        domain = path_segments[-1] if path_segments else parsed.netloc

        icon_link = soup.find("link", rel=lambda x: x and "icon" in x.lower())
        icon_href = icon_link.get("href") if icon_link else None

        if icon_href and icon_href.startswith("//"):
            icon_href = f"{parsed.scheme}:{icon_href}"
        elif icon_href and icon_href.startswith("/"):
            icon_href = f"{parsed.scheme}://{parsed.netloc}{icon_href}"

        return {
            "url": similarweb_url,
            "name": domain,
            "title": title,
            "description": description,
            "category": None,
            "icon": icon_href,
            "previewDesktop": None,
            "previewMobile": None,
        }

    @staticmethod
    def _extract_number_near_label(soup: BeautifulSoup, label: str) -> Optional[int]:
        candidate = soup.find(string=re.compile(label, re.IGNORECASE))
        if not candidate:
            return None
        text = candidate.parent.get_text(" ", strip=True) if candidate.parent else candidate
        match = re.search(r"([\d,]+)", text)
        if not match:
            return None
        return safe_int(match.group(1).replace(",", ""))

    @staticmethod
    def _extract_percentages_from_table(soup: BeautifulSoup, labels: Dict[str, str]) -> Dict[str, Optional[float]]:
        results: Dict[str, Optional[float]] = {key: None for key in labels.keys()}
        for key, label in labels.items():
            node = soup.find(string=re.compile(label, re.IGNORECASE))
            if not node:
                continue
            text = node.parent.get_text(" ", strip=True) if node.parent else node
            match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
            if match: