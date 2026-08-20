class WebSearchClient:
    """General web search adapter. Uses DDGS when installed; fails softly."""

    def __init__(self, max_results=5):
        self.max_results = max_results

    def search(self, query, max_results=None):
        query = (query or "").strip()
        if len(query) < 2:
            return []
        try:
            from ddgs import DDGS
        except ImportError:
            return []

        limit = max_results or self.max_results
        try:
            with DDGS() as ddgs:
                results = ddgs.text(query, max_results=limit)
                return [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href") or r.get("url") or "",
                        "snippet": r.get("body") or r.get("snippet") or "",
                        "source": "Web",
                    }
                    for r in results
                ]
        except Exception:
            return []
