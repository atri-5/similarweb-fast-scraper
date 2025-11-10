import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

def timestamp_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def safe_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None

def safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None

def normalize_domain(url_or_domain: str) -> str:
    """
    Normalize a URL or domain into a bare domain string suitable for Similarweb paths.
    Examples:
        "https://example.com"   -> "example.com"
        "example.com/"          -> "example.com"
        "http://www.example.org/path" -> "example.org"
    """
    text = url_or_domain.strip()

    if "://" not in text:
        # Assume bare domain.
        text = "http://" + text

    from urllib.parse import urlparse

    parsed = urlparse(text)
    host = parsed.netloc.lower()

    if host.startswith("www."):
        host = host[4:]

    # Drop port if present.
    if ":" in host:
        host = host.split(":", 1)[0]

    return host

def load_input_sites(path: Path) -> List[str]:
    sites: List[str] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                sites.append(stripped)
    except FileNotFoundError:
        logger.error("Input file not found: %s", path)
    except OSError as exc:
        logger.error("Error reading input file %s: %s", path, exc)
    return sites

def load_settings(path_str: str) -> Dict[str, Any]:
    path = Path(path_str)
    if not path.exists():
        logger.warning("Settings file not found at %s, using defaults.", path)
        return {
            "userAgent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "requestTimeoutSeconds": 15,
            "maxWorkers": 5,
            "similarwebBaseUrl": "https://www.similarweb.com/website",
        }

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in settings file %s: %s", path, exc)
        data = {}
    except OSError as exc:
        logger.error("Error reading settings file %s: %s", path, exc)
        data = {}

    defaults: Dict[str, Any] = {
        "userAgent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "requestTimeoutSeconds": 15,
        "maxWorkers": 5,
        "similarwebBaseUrl": "https://www.similarweb.com/website",
    }
    defaults.update(data)
    return defaults