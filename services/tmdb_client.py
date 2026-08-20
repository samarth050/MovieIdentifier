import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class TMDBClient:
    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

    def __init__(self, token=None, api_key=None):
        self.token = (
            token or os.getenv("TMDB_BEARER_TOKEN", "")
        ).strip()
        self.api_key = (
            api_key or os.getenv("TMDB_API_KEY", "")
        ).strip()
        self.session = requests.Session()
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def _headers(self):
        if self.token:
            return {
                "Authorization": f"Bearer {self.token}",
                "accept": "application/json",
            }
        return {"accept": "application/json"}

    def _request(self, path, params=None):
        params = dict(params or {})
        if not self.token:
            if not self.api_key:
                raise RuntimeError(
                    "TMDB credentials are not configured. "
                    "Set TMDB_BEARER_TOKEN or TMDB_API_KEY."
                )
            params["api_key"] = self.api_key

        try:
            response = self.session.get(
                self.BASE_URL + path,
                headers=self._headers(),
                params=params,
                timeout=(10, 30),
            )
        except requests.exceptions.SSLError as exc:
            raise RuntimeError(
                "TMDB HTTPS/TLS connection failed. "
                f"Details: {exc}"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                "TMDB connection was reset after retrying. "
                "Check your internet connection, proxy, or firewall and try again. "
                f"Details: {exc}"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                "TMDB request timed out after retrying. Check your internet connection."
            ) from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"TMDB request failed: {exc}") from exc
        if response.status_code != 200:
            raise RuntimeError(
                f"TMDB request failed ({response.status_code}): "
                f"{response.text[:300]}"
            )
        return response.json()

    def test_connection(self):
        data = self._request("/configuration")
        return bool(data.get("images"))

    def search_movies(self, query, max_results=5):
        query = (query or "").strip()
        if len(query) < 2:
            return []

        data = self._request(
            "/search/movie",
            {
                "query": query,
                "include_adult": "false",
                "language": "en-US",
                "page": 1,
            },
        )

        results = []
        for item in data.get("results", [])[:max_results]:
            results.append({
                "id": item.get("id"),
                "title": item.get("title"),
                "original_title": item.get("original_title"),
                "year": (
                    item.get("release_date", "")[:4]
                    if item.get("release_date") else ""
                ),
                "overview": item.get("overview", ""),
                "poster_path": item.get("poster_path"),
                "backdrop_path": item.get("backdrop_path"),
                "poster_url": (
                    self.IMAGE_BASE + item["poster_path"]
                    if item.get("poster_path") else ""
                ),
                "backdrop_url": (
                    self.IMAGE_BASE + item["backdrop_path"]
                    if item.get("backdrop_path") else ""
                ),
            })
        return results

    def find_by_imdb_id(self, imdb_id):
        """Resolve an IMDb title ID to its corresponding TMDB movie."""
        if not imdb_id:
            return None
        data = self._request(
            f"/find/{imdb_id}",
            {"external_source": "imdb_id", "language": "en-US"},
        )
        movies = data.get("movie_results", [])
        return self._normalize_movie(movies[0]) if movies else None

    def get_movie(self, movie_id):
        data = self._request(
            f"/movie/{movie_id}",
            {"language": "en-US"},
        )

        credits = self._request(
            f"/movie/{movie_id}/credits",
            {"language": "en-US"},
        )

        director = next(
            (
                c.get("name")
                for c in credits.get("crew", [])
                if c.get("job") == "Director"
            ),
            "",
        )

        cast = [
            c.get("name")
            for c in credits.get("cast", [])[:8]
            if c.get("name")
        ]

        return {
            "id": data.get("id"),
            "title": data.get("title"),
            "original_title": data.get("original_title"),
            "year": (
                data.get("release_date", "")[:4]
                if data.get("release_date") else ""
            ),
            "runtime": data.get("runtime"),
            "genres": [
                x.get("name") for x in data.get("genres", [])
            ],
            "overview": data.get("overview", ""),
            "rating": data.get("vote_average"),
            "vote_count": data.get("vote_count"),
            "director": director,
            "cast": cast,
            "poster_url": (
                self.IMAGE_BASE + data["poster_path"]
                if data.get("poster_path") else ""
            ),
            "backdrop_url": (
                self.IMAGE_BASE + data["backdrop_path"]
                if data.get("backdrop_path") else ""
            ),
        }

    def _normalize_movie(self, item):
        return {
            "id": item.get("id"),
            "title": item.get("title"),
            "original_title": item.get("original_title"),
            "year": (
                item.get("release_date", "")[:4]
                if item.get("release_date") else ""
            ),
            "overview": item.get("overview", ""),
            "poster_path": item.get("poster_path"),
            "backdrop_path": item.get("backdrop_path"),
            "poster_url": (
                self.IMAGE_BASE + item["poster_path"]
                if item.get("poster_path") else ""
            ),
            "backdrop_url": (
                self.IMAGE_BASE + item["backdrop_path"]
                if item.get("backdrop_path") else ""
            ),
        }
