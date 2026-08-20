import requests


class WikidataService:
    SEARCH_URL = "https://www.wikidata.org/w/api.php"

    def __init__(self, timeout=20):
        self.timeout = timeout

    def search(self, query, max_results=8):
        query = (query or "").strip()
        if not query:
            return []
        try:
            response = requests.get(
                self.SEARCH_URL,
                params={
                    "action": "wbsearchentities",
                    "search": query,
                    "language": "en",
                    "uselang": "en",
                    "format": "json",
                    "limit": max_results,
                },
                headers={"User-Agent": "MovieIdentifier/2.0"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise RuntimeError(f"Wikidata search failed: {exc}") from exc

        return [
            {
                "id": x.get("id"),
                "title": x.get("label") or "",
                "description": x.get("description") or "",
                "url": f"https://www.wikidata.org/wiki/{x.get('id')}" if x.get("id") else "",
            }
            for x in data.get("search", [])
        ]
