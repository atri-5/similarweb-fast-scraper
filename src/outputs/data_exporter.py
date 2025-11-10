import json
import logging
from pathlib import Path
from typing import Any, Iterable, List, Dict

logger = logging.getLogger(__name__)

class JSONDataExporter:
    """
    Handles writing scraped data to JSON files.
    """

    def export(self, records: Iterable[Dict[str, Any]], output_path: Path) -> None:
        # Ensure the parent directory exists
        output_path = output_path.resolve()
        if not output_path.parent.exists():
            logger.debug("Creating output directory: %s", output_path.parent)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to list to make sure we can safely serialize
        data: List[Dict[str, Any]] = list(records)

        try:
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except OSError as exc:  # noqa: BLE001
            logger.error("Failed to write JSON output to %s: %s", output_path, exc)
            raise

        logger.info("Successfully wrote %d record(s) to %s", len(data), output_path)