"""`datamap crawl <url> --out <folder>`: read a website into a folder of markdown notes.

Polite by default: stays on the starting site (same host, under the starting path),
follows robots.txt, waits between requests and stops after --max-pages. Each HTML page
becomes one note with front matter (type, title, resource = the page's address), ready
for `datamap okf`. Only crawl sites you own or have permission to read.
"""

from __future__ import annotations

import re
import time
import urllib.robotparser
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.request import Request, urlopen

import yaml

USER_AGENT = "datamap-crawler/0.1 (+https://github.com/Connoiter/claud_for_small_businesses_hackathon)"
NOT_PAGES = re.compile(
    r"\.(png|jpe?g|gif|svg|webp|ico|bmp|css|js|mjs|json|xml|rss|atom|zip|gz|tgz|rar|7z|"
    r"mp4|mov|webm|mp3|wav|woff2?|ttf|otf|eot|pdf|docx?|xlsx?|pptx?|csv)$",
    re.I,
)
MIN_WORDS = 30  # shorter pages are usually menus, redirects or empty templates
MAX_BYTES = 2_000_000


class _PageText(HTMLParser):
    """Readable text from one HTML page, as light markdown, plus its links."""

    SKIP = {"script", "style", "noscript", "svg", "template", "iframe", "form", "nav", "footer", "header", "aside"}
    BLOCKS = {"p", "div", "section", "article", "main", "li", "tr", "br", "blockquote", "pre",
              "h1", "h2", "h3", "h4", "h5", "h6", "dt", "dd", "figcaption", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self.links: list[str] = []
        self._skip = 0
        self._main = 0
        self._in_title = False
        self.all_parts: list[str] = []
        self.main_parts: list[str] = []

    def _emit(self, text: str) -> None:
        self.all_parts.append(text)
        if self._main:
            self.main_parts.append(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag == "meta" and (attrs.get("name") or attrs.get("property") or "").lower() in (
            "description", "og:description"
        ):
            self.description = self.description or (attrs.get("content") or "").strip()
        if tag == "title":
            self._in_title = True
        if tag in self.SKIP:
            self._skip += 1
        if tag in ("main", "article"):
            self._main += 1
        if self._skip:
            return
        if tag in self.BLOCKS:
            self._emit("\n")
        if tag in ("h1", "h2", "h3", "h4"):
            self._emit("#" * max(2, int(tag[1])) + " ")
        elif tag == "li":
            self._emit("- ")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        if tag in ("main", "article") and self._main:
            self._main -= 1
        if not self._skip and tag in self.BLOCKS:
            self._emit("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
            return
        if not self._skip and data.strip():
            self._emit(re.sub(r"\s+", " ", data))

    def markdown(self) -> str:
        parts = self.main_parts if len("".join(self.main_parts).split()) >= MIN_WORDS else self.all_parts
        lines = [line.strip() for line in "".join(parts).splitlines()]
        text = "\n".join(line for line in lines if line and line not in ("-", "##", "###", "####"))
        return re.sub(r"\n{3,}", "\n\n", text).strip()


def crawl(start: str, out: Path, max_pages: int = 150, delay: float = 0.3) -> int:
    """Write one markdown note per page under `out`; returns the number of pages written."""
    start = _normalise(start)
    site = urlparse(start)
    if site.scheme not in ("http", "https") or not site.netloc:
        raise SystemExit(f"{start} isn't a web address. Use one that starts with https://")
    scope = site.path if site.path.endswith("/") else site.path.rsplit("/", 1)[0] + "/"

    robots = _robots(f"{site.scheme}://{site.netloc}/robots.txt")

    out.mkdir(parents=True, exist_ok=True)
    queue, seen, written, names = deque([start]), {start}, 0, set()
    while queue and written < max_pages:
        url = queue.popleft()
        if robots is not None and not robots.can_fetch(USER_AGENT, url):
            continue
        page = _fetch(url)
        time.sleep(delay)
        if page is None:
            continue
        final_url, html = page
        parser = _PageText()
        try:
            parser.feed(html)
        except Exception:  # malformed markup: keep whatever was read
            pass

        for href in parser.links:
            link = _normalise(urljoin(final_url, href))
            p = urlparse(link)
            if (link not in seen and p.scheme in ("http", "https") and _same_site(p.netloc, site.netloc)
                    and p.path.startswith(scope) and not NOT_PAGES.search(p.path)):
                seen.add(link)
                queue.append(link)

        body = parser.markdown()
        if len(body.split()) < MIN_WORDS:
            continue
        title = re.sub(r"\s+", " ", parser.title).strip() or urlparse(final_url).path or site.netloc
        front = {"type": "Web Page", "title": title, "resource": final_url}
        if parser.description:
            front["description"] = parser.description
        path = out / _note_path(final_url, names)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n" + yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=10**6)
            + "---\n\n" + f"# {title}\n\n{body}\n",
            encoding="utf-8",
        )
        written += 1
        print(f"  {written:>3}  {final_url}")

    if not written:
        raise SystemExit(f"couldn't read any pages from {start} (blocked, empty, or not a website)")
    print(f"Wrote {written} pages to {out}" + (" (stopped at --max-pages)" if queue else ""))
    return written


def _robots(url: str) -> urllib.robotparser.RobotFileParser | None:
    """robots.txt, fetched with our own User-Agent (some sites 403 Python's default one).

    Rules apply when present; 401/403 means stay out; a missing file means no rules.
    """
    parser = urllib.robotparser.RobotFileParser(url)
    try:
        with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=15) as resp:
            parser.parse(resp.read(500_000).decode("utf-8", errors="replace").splitlines())
            return parser
    except HTTPError as e:
        if e.code in (401, 403):
            parser.disallow_all = True
            return parser
        return None
    except (URLError, OSError, ValueError):
        return None


def _fetch(url: str) -> tuple[str, str] | None:
    try:
        with urlopen(Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}), timeout=15) as resp:
            if "html" not in (resp.headers.get_content_type() or ""):
                return None
            raw = resp.read(MAX_BYTES)
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.geturl(), raw.decode(charset, errors="replace")
    except (HTTPError, URLError, OSError, ValueError, LookupError):
        return None


def _normalise(url: str) -> str:
    url = urldefrag(url.strip())[0]
    p = urlparse(url)
    if not p.scheme:
        return _normalise("https://" + url)
    path = p.path or "/"
    return p._replace(netloc=p.netloc.lower(), path=path, params="").geturl()


def _same_site(a: str, b: str) -> bool:
    strip = lambda h: h.lower().removeprefix("www.")
    return strip(a) == strip(b)


def _note_path(url: str, taken: set[str]) -> str:
    p = urlparse(url)
    segments = [re.sub(r"[^\w-]+", "-", s).strip("-").lower() for s in p.path.split("/") if s]
    segments = [s for s in segments if s] or ["home"]
    if p.query:
        segments[-1] += "-" + re.sub(r"[^\w-]+", "-", p.query).strip("-").lower()[:40]
    if segments[-1] in ("index", "log"):  # reserved by OKF
        segments[-1] += "-page"
    name = "/".join(segments)
    candidate, n = name, 2
    while candidate in taken:
        candidate, n = f"{name}-{n}", n + 1
    taken.add(candidate)
    return candidate + ".md"
