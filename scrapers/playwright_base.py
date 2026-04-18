"""Base class for Playwright-based scrapers that bypass Cloudflare JS challenges.

Uses playwright-stealth to minimize bot-detection fingerprinting.

Extraction strategy per query (in order):
  1. JSON-LD schema.org structured data  (most reliable)
  2. CSS selector patterns               (site-specific)
  3. Inline JSON blobs                   (last resort)

Falls back gracefully to [] when playwright is not installed.
"""
import asyncio
import json
import re
import unicodedata
import urllib.parse
from difflib import SequenceMatcher
from typing import Optional

from domain.models import ScrapedProduct
from scrapers.base import BaseScraper


def _norm(text: str) -> str:
    return (
        unicodedata.normalize("NFD", text)
        .encode("ascii", "ignore")
        .decode()
        .lower()
        .strip()
    )


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


class PlaywrightBaseScraper(BaseScraper):
    """Subclasses must define the class attributes below.

    _SEARCH_URL_TEMPLATE  URL with a ``{query}`` placeholder (already URL-encoded
                          by this base before substitution).
    _WAIT_SELECTOR        CSS selector to wait for after navigation (optional).
    _PRODUCT_SELECTORS    List of CSS selectors to try for product containers.
    _NAME_SELECTORS       List of CSS selectors for the product name (within container).
    _PRICE_SELECTORS      List of CSS selectors for the price (within container).
    _COOKIE_SELECTOR      CSS selector for the site-specific cookie-accept button.
    _MIN_SCORE            Minimum fuzzy-match score to accept a result (0–1).
    """

    _SEARCH_URL_TEMPLATE: str = ""
    _WAIT_SELECTOR: Optional[str] = None
    _PRODUCT_SELECTORS: list[str] = []
    _NAME_SELECTORS: list[str] = []
    _PRICE_SELECTORS: list[str] = []
    _COOKIE_SELECTOR: Optional[str] = None
    _MIN_SCORE: float = 0.25

    # ── Public sync entry point ───────────────────────────────────────────────

    def scrape_products(self, queries: list[str]) -> list[ScrapedProduct]:
        try:
            return asyncio.run(self._async_scrape(queries))
        except ImportError as exc:
            print(f"[{self.NOMBRE}] playwright not installed — skipping. ({exc})")
            return []
        except Exception as exc:
            print(f"[{self.NOMBRE}] Playwright error: {exc}")
            return []

    # ── Async Playwright orchestration ────────────────────────────────────────

    async def _async_scrape(self, queries: list[str]) -> list[ScrapedProduct]:
        from playwright.async_api import async_playwright

        results: list[ScrapedProduct] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--window-size=1366,768",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="es-ES",
                timezone_id="Europe/Madrid",
                viewport={"width": 1366, "height": 768},
                extra_http_headers={
                    "Accept-Language": "es-ES,es;q=0.9",
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        "application/xml;q=0.9,*/*;q=0.8"
                    ),
                },
            )

            # Stealth patches: hide navigator.webdriver, fix plugins list, etc.
            try:
                from playwright_stealth import stealth_async
                page = await context.new_page()
                await stealth_async(page)
            except ImportError:
                page = await context.new_page()

            page.on("console", lambda _: None)  # suppress noisy logs

            # First load: navigate + dismiss cookies once
            if queries:
                first_url = self._build_url(queries[0])
                await self._load_and_accept_cookies(page, first_url)
                products = await self._extract_from_page(page, queries[0])
                best = self._best_match(queries[0], products)
                if best:
                    results.append(self._to_scraped(queries[0], best))
                else:
                    print(f"[{self.NOMBRE}] Not found: {queries[0]!r}")

            for query in queries[1:]:
                url = self._build_url(query)
                products = await self._search_query(page, url, query)
                best = self._best_match(query, products)
                if best:
                    results.append(self._to_scraped(query, best))
                else:
                    print(f"[{self.NOMBRE}] Not found: {query!r}")

            await browser.close()

        return results

    def _build_url(self, query: str) -> str:
        return self._SEARCH_URL_TEMPLATE.format(query=urllib.parse.quote(query))

    async def _load_and_accept_cookies(self, page, url: str) -> None:
        """Navigate to *url* and dismiss any cookie consent banner."""
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(2_000)
        except Exception:
            return

        # Site-specific button first
        for sel in filter(None, [
            self._COOKIE_SELECTOR,
            "#onetrust-accept-btn-handler",
            "button[id*='accept']",
            "button[class*='accept']",
            "[data-testid='accept-cookies']",
            ".cookie-consent__accept",
            "button:has-text('Aceptar todo')",
            "button:has-text('Aceptar')",
            "button:has-text('Acepto')",
            "button:has-text('Accept')",
        ]):
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    await page.wait_for_timeout(800)
                    break
            except Exception:
                continue

    async def _search_query(self, page, url: str, query: str) -> list[dict]:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            if self._WAIT_SELECTOR:
                try:
                    await page.wait_for_selector(self._WAIT_SELECTOR, timeout=8_000)
                except Exception:
                    pass
            else:
                await page.wait_for_timeout(2_500)
        except Exception as exc:
            print(f"[{self.NOMBRE}] Nav error for {query!r}: {exc}")
            return []

        # Detect Cloudflare challenge
        title = (await page.title()).lower()
        if "just a moment" in title or "cloudflare" in title:
            print(f"[{self.NOMBRE}] Cloudflare challenge for {query!r} — waiting 8 s…")
            await page.wait_for_timeout(8_000)

        return await self._extract_from_page(page, query)

    async def _extract_from_page(self, page, query: str) -> list[dict]:
        products = await self._extract_jsonld(page)
        if products:
            return products
        products = await self._extract_css(page)
        if products:
            return products
        return await self._extract_inline_json(page)

    # ── JSON-LD extraction ────────────────────────────────────────────────────

    async def _extract_jsonld(self, page) -> list[dict]:
        try:
            scripts = await page.query_selector_all('script[type="application/ld+json"]')
            products: list[dict] = []
            for script in scripts:
                try:
                    data = json.loads(await script.inner_text())
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        t = item.get("@type", "")
                        if t == "Product":
                            p = self._parse_jsonld_product(item)
                            if p:
                                products.append(p)
                        elif t in ("ItemList", "SearchResultsPage", "CollectionPage"):
                            for el in item.get("itemListElement", []):
                                if not isinstance(el, dict):
                                    continue
                                inner = el.get("item", el)
                                if isinstance(inner, dict) and inner.get("@type") == "Product":
                                    p = self._parse_jsonld_product(inner)
                                    if p:
                                        products.append(p)
                except Exception:
                    continue
            return products
        except Exception:
            return []

    def _parse_jsonld_product(self, item: dict) -> Optional[dict]:
        nombre = (item.get("name") or "").strip()
        if not nombre:
            return None
        offers = item.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if not isinstance(offers, dict):
            return None
        raw_price = offers.get("price") or offers.get("lowPrice")
        if raw_price is None:
            return None
        try:
            precio = float(str(raw_price).replace(",", "."))
        except (ValueError, TypeError):
            return None
        if precio <= 0:
            return None
        imagen = item.get("image")
        if isinstance(imagen, list):
            imagen = imagen[0] if imagen else None
        categoria = item.get("category")
        if isinstance(categoria, dict):
            categoria = categoria.get("name")
        return {
            "nombre": nombre,
            "precio": precio,
            "ean": item.get("gtin13") or item.get("gtin") or item.get("sku"),
            "url_imagen": imagen,
            "url_producto": item.get("url"),
            "categoria": str(categoria) if categoria else None,
        }

    # ── CSS selector extraction ───────────────────────────────────────────────

    async def _extract_css(self, page) -> list[dict]:
        for container_sel in self._PRODUCT_SELECTORS:
            try:
                containers = await page.query_selector_all(container_sel)
                if not containers:
                    continue
                products: list[dict] = []
                for c in containers[:20]:
                    nombre, precio = None, None
                    for ns in self._NAME_SELECTORS:
                        el = await c.query_selector(ns)
                        if el:
                            nombre = (await el.inner_text()).strip()
                            if nombre:
                                break
                    for ps in self._PRICE_SELECTORS:
                        el = await c.query_selector(ps)
                        if el:
                            raw = (await el.inner_text()).strip()
                            precio = self._parse_price(raw)
                            if precio:
                                break
                    if nombre and precio and precio > 0:
                        products.append({"nombre": nombre, "precio": precio})
                if products:
                    return products
            except Exception:
                continue
        return []

    # ── Inline JSON extraction ────────────────────────────────────────────────

    async def _extract_inline_json(self, page) -> list[dict]:
        try:
            content = await page.content()
            for pat in [
                r'"products"\s*:\s*(\[.*?\])',
                r'"items"\s*:\s*(\[.*?\])',
                r'"results"\s*:\s*(\[.*?\])',
                r'"hits"\s*:\s*(\[.*?\])',
            ]:
                m = re.search(pat, content, re.DOTALL)
                if not m:
                    continue
                try:
                    items = json.loads(m.group(1))
                    products: list[dict] = []
                    for raw in items[:20]:
                        if not isinstance(raw, dict):
                            continue
                        nombre = (
                            raw.get("name") or raw.get("title")
                            or raw.get("displayName") or ""
                        ).strip()
                        price_raw = (
                            raw.get("price") or raw.get("priceValue")
                            or raw.get("currentPrice") or raw.get("salePrice")
                        )
                        if isinstance(price_raw, dict):
                            price_raw = price_raw.get("value") or price_raw.get("price")
                        if nombre and price_raw is not None:
                            try:
                                products.append({
                                    "nombre": nombre,
                                    "precio": float(str(price_raw).replace(",", ".")),
                                    "ean": raw.get("ean") or raw.get("barcode"),
                                    "url_imagen": raw.get("image") or raw.get("thumbnail"),
                                    "url_producto": raw.get("url") or raw.get("productUrl"),
                                })
                            except (ValueError, TypeError):
                                pass
                    if products:
                        return products
                except json.JSONDecodeError:
                    continue
        except Exception:
            pass
        return []

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_price(raw: str) -> Optional[float]:
        cleaned = re.sub(r"[^\d,\.]", "", raw.replace("€", "").strip())
        if not cleaned:
            return None
        # Handle "1.234,56" European format
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def _best_match(self, query: str, candidates: list[dict]) -> Optional[dict]:
        if not candidates:
            return None
        qn = _norm(query)
        qw = set(qn.split())
        best_score, best = 0.0, None
        for p in candidates:
            nn = _norm(p.get("nombre", ""))
            sim = _similarity(query, p.get("nombre", ""))
            overlap = len(qw & set(nn.split()))
            total = sim + (overlap / max(len(qw), 1)) * 0.30
            if total > best_score:
                best_score, best = total, p
        return best if best_score >= self._MIN_SCORE else None

    @staticmethod
    def _to_scraped(query: str, p: dict) -> ScrapedProduct:
        return ScrapedProduct(
            nombre=p["nombre"],
            precio=p["precio"],
            moneda="EUR",
            ean=p.get("ean"),
            categoria=p.get("categoria"),
            unidad_medida=p.get("unidad_medida"),
            url_imagen=p.get("url_imagen"),
            url_producto=p.get("url_producto"),
            disponible=True,
            nombre_buscado=query,
        )
