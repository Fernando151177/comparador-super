"""Abstract base class for all supermarket scrapers.

To add a new scraper:
1. Subclass ``BaseScraper``.
2. Set ``NOMBRE``, ``CODIGO`` and ``PAIS`` class attributes.
3. Implement ``scrape_products(queries)``.
4. Register the class in ``utils/scheduler.py``.
"""
import time
from abc import ABC, abstractmethod
from typing import Optional

import requests

from domain.models import ScrapedProduct
from utils import config
from utils.user_agents import get_headers


class BaseScraper(ABC):
    """Common HTTP layer, rate limiting and retry logic for all scrapers."""

    NOMBRE: str = "Base"      # Human-readable name shown in logs and UI
    CODIGO: str = "BASE"      # Matches supermercados.codigo in the DB
    PAIS: str = "ES"          # 'ES' | 'PT'

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(get_headers())
        self._supermarket_id: Optional[int] = None

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def supermarket_id(self) -> int:
        """Lazily fetches the supermarket's DB id (cached after first call)."""
        if self._supermarket_id is None:
            self._supermarket_id = self._fetch_supermarket_id()
        return self._supermarket_id

    def run(self, queries: Optional[list[str]] = None) -> list[ScrapedProduct]:
        """Entry point called by the scheduler.

        If *queries* is None the scraper decides what to fetch (e.g. full
        catalogue download).  Otherwise it searches for each query string.
        """
        print(f"[{self.NOMBRE}] Starting scrape…")
        results = self.scrape_products(queries or [])
        print(f"[{self.NOMBRE}] Done — {len(results)} products found.")
        return results

    @abstractmethod
    def scrape_products(self, queries: list[str]) -> list[ScrapedProduct]:
        """Fetch prices for the given query strings.

        Args:
            queries: Product names / search terms to look up.

        Returns:
            List of ScrapedProduct objects.  The scraper must NOT write to the
            database; that is the scheduler's responsibility.
        """
        ...

    # ── HTTP helpers ─────────────────────────────────────────────────────────

    def get(
        self,
        url: str,
        params: Optional[dict] = None,
        extra_headers: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> Optional[requests.Response]:
        """GET with exponential back-off retries.

        Returns None after ``MAX_RETRIES`` failed attempts (no exception raised
        so that one bad product does not abort the whole scrape run).
        """
        if extra_headers:
            self.session.headers.update(extra_headers)

        for attempt in range(config.MAX_RETRIES):
            try:
                resp = self.session.get(
                    url,
                    params=params,
                    timeout=timeout or config.REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                self._rate_limit()
                return resp
            except requests.RequestException as exc:
                delay = config.BASE_RETRY_DELAY * (2 ** attempt)
                print(f"[{self.NOMBRE}] Attempt {attempt + 1} failed: {exc}. Waiting {delay}s…")
                time.sleep(delay)

        print(f"[{self.NOMBRE}] All {config.MAX_RETRIES} attempts failed for {url}")
        return None

    def post(
        self,
        url: str,
        json: Optional[dict] = None,
        data: Optional[dict] = None,
        extra_headers: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> Optional[requests.Response]:
        """POST with the same retry logic as ``get``."""
        if extra_headers:
            self.session.headers.update(extra_headers)

        for attempt in range(config.MAX_RETRIES):
            try:
                resp = self.session.post(
                    url,
                    json=json,
                    data=data,
                    timeout=timeout or config.REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                self._rate_limit()
                return resp
            except requests.RequestException as exc:
                delay = config.BASE_RETRY_DELAY * (2 ** attempt)
                print(f"[{self.NOMBRE}] POST attempt {attempt + 1} failed: {exc}. Waiting {delay}s…")
                time.sleep(delay)

        return None

    # ── Internals ─────────────────────────────────────────────────────────────

    def _rate_limit(self) -> None:
        """Polite pause between requests."""
        time.sleep(config.RATE_LIMIT_DELAY)

    def _rotate_user_agent(self) -> None:
        """Picks a fresh random User-Agent for the next request."""
        from utils.user_agents import get_random
        self.session.headers["User-Agent"] = get_random()

    def _fetch_supermarket_id(self) -> int:
        """Looks up the supermarket id from the DB by CODIGO."""
        from database.connection import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM supermercados WHERE codigo = ?", (self.CODIGO,)
            ).fetchone()
        if row is None:
            raise RuntimeError(
                f"Supermarket '{self.CODIGO}' not found in DB. Did you run init_db()?"
            )
        return row["id"]
