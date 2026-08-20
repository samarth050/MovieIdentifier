import requests

try:
    from ddgs import DDGS
except ImportError:  # older package name
    DDGS = None


class WebSearchService:
    """General web-search adapter used only for metadata/candidate discovery."""

    def __init__(self, timeout=20):
        self.timeout = timeout

    def search(self, query, max_results=6, domains=None):
        query = (query or "").strip()
        if not query:
            return []

        if DDGS is not None:
            try:
                with DDGS(timeout=self.timeout) as ddgs:
                    q = query
                    if domains:
                        q += " " + " ".join(f"site:{d}" for d in domains)
                    rows = list(ddgs.text(q, max_results=max_results))
                    return [
                        {
                            "title": r.get("title", ""),
                            "url": r.get("href") or r.get("url") or "",
                            "snippet": r.get("body") or r.get("snippet") or "",
                        }
                        for r in rows
                    ]
            except Exception:
                pass

        # Fallback to DuckDuckGo HTML if the ddgs package is unavailable.
        try:
            q = query
            if domains:
                q += " " + " ".join(f"site:{d}" for d in domains)
            response = requests.get(
                "https://html.duckduckgo.com/html/",
                params={"q": q},
                headers={"User-Agent": "MovieIdentifier/2.0"},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except Exception as exc:
            raise RuntimeError(f"Web search failed: {exc}") from exc

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for item in soup.select(".result")[:max_results]:
            a = item.select_one(".result__a")
            snippet = item.select_one(".result__snippet")
            if a:
                results.append({
                    "title": a.get_text(" ", strip=True),
                    "url": a.get("href", ""),
                    "snippet": snippet.get_text(" ", strip=True) if snippet else "",
                })
        return results
