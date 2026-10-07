"""Lightweight HTTP website crawler (httpx). No Playwright required for Phase 2."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.services.website.url_safety import (
    UnsafeURLError,
    absolutize,
    assert_public_url,
    normalize_website_url,
    same_registrable_host,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_PAGES = 5
DEFAULT_MAX_DEPTH = 2
DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_BYTES = 1_500_000
DEFAULT_MAX_REDIRECTS = 5
USER_AGENT = "LeadFlowBot/0.2 (+https://leadflow.local; lead-qualification)"


@dataclass
class FetchedPage:
    url: str
    final_url: str
    status_code: int
    html: str
    load_time_ms: int
    page_size_bytes: int
    https_enabled: bool
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class CrawlResult:
    start_url: str
    reachable: bool
    blocked: bool = False
    error_message: str | None = None
    pages: list[FetchedPage] = field(default_factory=list)
    http_status: int | None = None
    final_url: str | None = None
    https_enabled: bool | None = None
    load_time_ms: int | None = None


FetchFn = Callable[[str], FetchedPage]


class WebsiteCrawler:
    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        max_pages: int = DEFAULT_MAX_PAGES,
        max_depth: int = DEFAULT_MAX_DEPTH,
        timeout: float = DEFAULT_TIMEOUT,
        max_bytes: int = DEFAULT_MAX_BYTES,
        respect_robots: bool = True,
        resolve_dns: bool = True,
        fetch_fn: FetchFn | None = None,
    ):
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.respect_robots = respect_robots
        self.resolve_dns = resolve_dns
        self._client = client
        self._owns_client = client is None
        self._fetch_fn = fetch_fn
        self._robots_cache: dict[str, RobotFileParser | None] = {}

    def __enter__(self) -> WebsiteCrawler:
        if self._client is None and self._fetch_fn is None:
            # Manual redirect following so each hop is SSRF-checked
            self._client = httpx.Client(
                timeout=self.timeout,
                follow_redirects=False,
                headers={"User-Agent": USER_AGENT},
            )
        return self

    def __exit__(self, *args: object) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def crawl(self, raw_url: str) -> CrawlResult:
        try:
            start = normalize_website_url(raw_url)
            if not start:
                return CrawlResult(start_url="", reachable=False, error_message="Empty website URL")
            assert_public_url(start, resolve_dns=self.resolve_dns)
        except UnsafeURLError as exc:
            return CrawlResult(start_url=raw_url or "", reachable=False, error_message=str(exc))

        if self.respect_robots and not self._allowed_by_robots(start):
            return CrawlResult(
                start_url=start,
                reachable=False,
                blocked=True,
                error_message="Blocked by robots.txt",
            )

        pages: list[FetchedPage] = []
        queue: list[tuple[str, int]] = [(start, 0)]
        seen: set[str] = set()

        while queue and len(pages) < self.max_pages:
            url, depth = queue.pop(0)
            key = url.split("#")[0].rstrip("/").lower()
            if key in seen:
                continue
            seen.add(key)

            try:
                assert_public_url(url, resolve_dns=self.resolve_dns)
                page = self._fetch(url)
            except UnsafeURLError as exc:
                if not pages:
                    return CrawlResult(start_url=start, reachable=False, error_message=str(exc))
                continue
            except httpx.TimeoutException:
                if not pages:
                    return CrawlResult(start_url=start, reachable=False, error_message="Request timed out")
                continue
            except httpx.HTTPError as exc:
                if not pages:
                    return CrawlResult(
                        start_url=start,
                        reachable=False,
                        error_message="Website unreachable",
                    )
                logger.info("Skip page fetch error url=%s err=%s", url, type(exc).__name__)
                continue

            pages.append(page)

            if depth < self.max_depth and len(pages) < self.max_pages:
                for link in self._extract_internal_links(page):
                    link_key = link.split("#")[0].rstrip("/").lower()
                    if link_key not in seen:
                        queue.append((link, depth + 1))

        if not pages:
            return CrawlResult(start_url=start, reachable=False, error_message="Website unreachable")

        home = pages[0]
        return CrawlResult(
            start_url=start,
            reachable=True,
            pages=pages,
            http_status=home.status_code,
            final_url=home.final_url,
            https_enabled=home.https_enabled,
            load_time_ms=home.load_time_ms,
        )

    def fetch_url_list(self, raw_base: str, paths: list[str]) -> CrawlResult:
        """Fetch a limited set of same-site paths (used by contact discovery)."""
        try:
            base = normalize_website_url(raw_base)
            if not base:
                return CrawlResult(start_url="", reachable=False, error_message="Empty website URL")
            assert_public_url(base, resolve_dns=self.resolve_dns)
        except UnsafeURLError as exc:
            return CrawlResult(start_url=raw_base or "", reachable=False, error_message=str(exc))

        from urllib.parse import urljoin

        candidates: list[str] = []
        seen: set[str] = set()
        for path in paths:
            if path in {"", "/"}:
                url = base
            else:
                url = urljoin(base if base.endswith("/") else base + "/", path.lstrip("/"))
            key = url.split("#")[0].rstrip("/").lower()
            if key in seen:
                continue
            if not same_registrable_host(base, url):
                continue
            seen.add(key)
            candidates.append(url)

        pages: list[FetchedPage] = []
        for url in candidates[: self.max_pages]:
            if self.respect_robots and not self._allowed_by_robots(url):
                continue
            try:
                assert_public_url(url, resolve_dns=self.resolve_dns)
                page = self._fetch(url)
            except UnsafeURLError:
                continue
            except httpx.TimeoutException:
                if not pages:
                    return CrawlResult(start_url=base, reachable=False, error_message="Request timed out")
                continue
            except httpx.HTTPError:
                continue
            if page.status_code >= 400 and not page.html:
                continue
            pages.append(page)

        if not pages:
            return CrawlResult(start_url=base, reachable=False, error_message="Website unreachable")

        home = pages[0]
        return CrawlResult(
            start_url=base,
            reachable=True,
            pages=pages,
            http_status=home.status_code,
            final_url=home.final_url,
            https_enabled=home.https_enabled,
            load_time_ms=home.load_time_ms,
        )

    def _fetch(self, url: str) -> FetchedPage:
        if self._fetch_fn is not None:
            return self._fetch_fn(url)
        if self._client is None:
            raise RuntimeError("HTTP client is not initialized")

        started = time.perf_counter()
        current = url
        assert_public_url(current, resolve_dns=self.resolve_dns)

        for _ in range(DEFAULT_MAX_REDIRECTS + 1):
            with self._client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise UnsafeURLError("Redirect without Location header")
                    nxt = absolutize(current, location) or location
                    assert_public_url(nxt, resolve_dns=self.resolve_dns)
                    current = nxt
                    continue

                assert_public_url(str(response.url), resolve_dns=self.resolve_dns)
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > self.max_bytes:
                        break
                    chunks.append(chunk)
                body = b"".join(chunks)
                elapsed = int((time.perf_counter() - started) * 1000)
                content_type = response.headers.get("content-type", "")
                html = ""
                if "html" in content_type.lower() or body[:200].lstrip().startswith(
                    (b"<!DOCTYPE", b"<html", b"<HTML")
                ):
                    html = body.decode(response.encoding or "utf-8", errors="replace")
                final = str(response.url)
                return FetchedPage(
                    url=url,
                    final_url=final,
                    status_code=response.status_code,
                    html=html,
                    load_time_ms=elapsed,
                    page_size_bytes=len(body),
                    https_enabled=urlparse(final).scheme.lower() == "https",
                    headers={k.lower(): v for k, v in response.headers.items()},
                )

        raise UnsafeURLError("Too many redirects")

    def _allowed_by_robots(self, url: str) -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robots_cache:
            robots_url = f"{base}/robots.txt"
            parser = RobotFileParser()
            try:
                if self._fetch_fn is not None:
                    # Tests / offline: allow by default unless robots page provided
                    self._robots_cache[base] = None
                    return True
                assert self._client is not None
                resp = self._client.get(robots_url)
                if resp.status_code >= 400:
                    self._robots_cache[base] = None
                else:
                    parser.parse(resp.text.splitlines())
                    self._robots_cache[base] = parser
            except Exception:
                self._robots_cache[base] = None
                return True

        parser = self._robots_cache[base]
        if parser is None:
            return True
        return parser.can_fetch(USER_AGENT, url)

    def _extract_internal_links(self, page: FetchedPage) -> list[str]:
        from bs4 import BeautifulSoup

        if not page.html:
            return []
        soup = BeautifulSoup(page.html, "lxml")
        links: list[str] = []
        for a in soup.find_all("a", href=True):
            abs_url = absolutize(page.final_url, a["href"])
            if not abs_url:
                continue
            if not same_registrable_host(page.final_url, abs_url):
                continue
            if urlparse(abs_url).scheme not in {"http", "https"}:
                continue
            links.append(abs_url)
            if len(links) >= 20:
                break
        return links
