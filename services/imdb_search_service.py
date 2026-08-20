import re

from services.web_search_client import WebSearchClient


class IMDbSearchService:
    """Find public IMDb title references through a general web-search provider.

    This deliberately does not scrape IMDb pages. Results are only used as
    corroborating evidence and are later resolved to a TMDB item by IMDb ID.
    """

    ID_PATTERN = re.compile(r"imdb\.com/title/(tt\d+)", re.IGNORECASE)
    TITLE_PATTERN = re.compile(
        r"^(?P<title>.+?)\s*\((?P<year>\d{4})(?:\s*[IVX]+)?\)\s*-\s*IMDb",
        re.IGNORECASE,
    )

    def __init__(self, web_search=None):
        self.web_search = web_search or WebSearchClient()

    def search_movies(self, query, max_results=3):
        query = (query or "").strip()
        if len(query) < 2:
            return []

        rows = self.web_search.search(
            f'site:imdb.com/title "{query}"',
            max_results=max_results,
        )
        results, seen = [], set()
        for row in rows:
            url = row.get("url", "")
            match = self.ID_PATTERN.search(url)
            if not match or match.group(1) in seen:
                continue
            seen.add(match.group(1))
            page_title = (row.get("title") or "").strip()
            title_match = self.TITLE_PATTERN.match(page_title)
            results.append({
                "imdb_id": match.group(1),
                "title": title_match.group("title").strip() if title_match else page_title,
                "year": title_match.group("year") if title_match else "",
                "url": url,
                "snippet": row.get("snippet") or "",
            })
        return results
