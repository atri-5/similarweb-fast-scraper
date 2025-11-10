URRENT_FILE = Path(__file__).resolve()
SRC_ROOT = CURRENT_FILE.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from extractors.similarweb_parser import SimilarwebScraper  # noqa: E402
from extractors.utils_data import (  # noqa: E402
    load_input_sites,
    load_settings,
    timestamp_now_iso,
)
from outputs.data_exporter import JSONDataExporter  # noqa: E402

def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Similarweb Fast Scraper - scrape Similarweb metrics for a list of sites."
    )
    parser.add_argument(
        "-i",
        "--input",
        default=str(Path("data") / "input_sites.txt"),
        help="Path to a text file containing one target URL or domain per line.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=str(Path("data") / "sample_output.json"),
        help="Path where the JSON output will be written.",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=str(Path("src") / "config" / "settings.example.json"),
        help="Path to settings JSON file (see src/config/settings.example.json).",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Override max worker threads for scraping (defaults to config value).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging.",
    )
    return parser.parse_args()

def scrape_bulk(
    targets: List[str],
    scraper: SimilarwebScraper,
    max_workers: int,
    logger: logging.Logger,
) -> List[Dict[str, Any]]:
    if not targets:
        logger.warning("No targets found in input file. Exiting.")
        return []

    results: List[Dict[str, Any]] = []
    logger.info("Starting scrape for %d target(s) using %d worker(s)", len(targets), max_workers)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(scraper.scrape_site, target): target for target in targets}
        for future in as_completed(future_map):
            target = future_map[future]
            try:
                data = future.result()
                results.append(data)
                logger.info("Finished scraping: %s", target)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Error scraping %s: %s", target, exc)

    logger.info("Scraping finished. Successfully scraped %d/%d target(s).", len(results), len(targets))
    return results

def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)
    logger = logging.getLogger("main")

    settings = load_settings(args.config)
    if args.max_workers is not None and args.max_workers > 0:
        settings["maxWorkers"] = args.max_workers

    max_workers = int(settings.get("maxWorkers", 5))
    timeout = float(settings.get("requestTimeoutSeconds", 15))
    base_url = settings.get("similarwebBaseUrl", "https://www.similarweb.com/website")
    user_agent = settings.get(
        "userAgent",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    )

    logger.debug("Using settings: %s", settings)

    input_path = Path(args.input)
    output_path = Path(args.output)

    targets = load_input_sites(input_path)
    logger.info("Loaded %d target(s) from %s", len(targets), input_path)

    scraper = SimilarwebScraper(
        base_url=base_url,
        user_agent=user_agent,
        timeout=timeout,
    )

    data = scrape_bulk(targets, scraper, max_workers, logger)

    if data:
        # Add snapshotDate if not present in objects
        snapshot_date = settings.get("snapshotDate")
        if not snapshot_date:
            snapshot_date = timestamp_now_iso()[:10]  # YYYY-MM-DD

        for item in data:
            item.setdefault("snapshotDate", snapshot_date)
            item.setdefault("scrapedAt", timestamp_now_iso())

        exporter = JSONDataExporter()
        exporter.export(data, output_path)
        logger.info("Exported %d record(s) to %s", len(data), output_path)
    else:
        logger.warning("No data was scraped. Nothing will be exported.")

if __name__ == "__main__":
    main()