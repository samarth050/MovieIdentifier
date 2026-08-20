import requests
from urllib.parse import quote_plus


class AdultVintageSources:
    """Optional adult/vintage metadata adapters.

    IAFD is deliberately web-search based; no IAFD API key is required.
    AFDB is optional and uses the unofficial MyAPIFilms AFDB API when a token
    is supplied by the user.
    """

    def __init__(self, web_search, afdb_token=""):
        self.web = web_search
        self.afdb_token = (afdb_token or "").strip()

    def search_iafd(self, query, max_results=5):
        # Do not scrape or require an IAFD API. Find publicly indexed IAFD pages.
        results = self.web.search(
            f'site:iafd.com "{query}"', max_results=max_results
        )
        output = []
        for item in results:
            url = item.get("url", "")
            if "iafd.com" not in url.lower():
                continue
            output.append({
                "source": "IAFD",
                "source_id": url,
                "id": f"iafd:{url}",
                "title": item.get("title") or query,
                "year": "",
                "overview": item.get("snippet", ""),
                "source_url": url,
                "web_url": url,
                "adult_source": True,
            })
        return output

    def search_afdb(self, query, max_results=5):
        if not self.afdb_token:
            return []

        # MyAPIFilms documents the AFDB title-search endpoint as afdb.do.
        params = {
            "title": query,
            "format": "json",
            "token": self.afdb_token,
        }
        try:
            response = requests.get(
                "https://www.myapifilms.com/afdb.do",
                params=params,
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []

        if isinstance(data, dict):
            if data.get("error") or data.get("code") == 513:
                return []
            items = data.get("movies") or data.get("results") or data.get("data") or []
        elif isinstance(data, list):
            items = data
        else:
            items = []

        output = []
        for item in items[:max_results]:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("name") or query
            movie_id = item.get("videoidId") or item.get("idMovie") or item.get("id") or ""
            output.append({
                "source": "AFDB",
                "source_id": str(movie_id),
                "id": f"afdb:{movie_id or title}",
                "title": title,
                "year": str(item.get("year") or ""),
                "overview": item.get("description") or "",
                "source_url": item.get("url") or "",
                "web_url": item.get("url") or "",
                "poster_url": item.get("urlPosterFront") or item.get("urlPosterBack") or "",
                "adult_source": True,
            })
        return output
