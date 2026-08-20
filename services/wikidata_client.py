import requests


class WikidataClient:
    API = "https://www.wikidata.org/w/api.php"

    def search_movies(self, query, max_results=5):
        query = (query or "").strip()
        if len(query) < 2:
            return []
        params = {
            "action": "wbsearchentities",
            "search": query,
            "language": "en",
            "uselang": "en",
            "type": "item",
            "limit": max_results,
            "format": "json",
        }
        try:
            response = requests.get(self.API, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []

        results = []
        for item in data.get("search", []):
            results.append({
                "source": "Wikidata",
                "source_id": item.get("id", ""),
                "title": item.get("label") or query,
                "year": "",
                "overview": item.get("description", ""),
                "source_url": f"https://www.wikidata.org/wiki/{item.get('id', '')}",
                "web_url": f"https://www.wikidata.org/wiki/{item.get('id', '')}",
                "id": f"wikidata:{item.get('id', '')}",
            })
        return results
