import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class TMDBService:
    """Small, GUI-friendly TMDB connectivity/search service."""

    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, bearer_token=None, api_key=None):
        self.bearer_token = (bearer_token or os.getenv("TMDB_BEARER_TOKEN", "")).strip()
        self.api_key = (api_key or os.getenv("TMDB_API_KEY", "")).strip()
        self.session = requests.Session()
        retry = Retry(
            total=2,
            connect=2,
            read=2,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def _headers(self):
        headers = {"accept": "application/json"}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers

    def _request(self, path, params=None):
        params = dict(params or {})
        if not self.bearer_token and not self.api_key:
            raise RuntimeError(
                "TMDB credentials are not configured. "
                "Open Settings and enter the TMDB API Read Access Token."
            )
        if not self.bearer_token:
            params["api_key"] = self.api_key

        url = self.BASE_URL + path
        try:
            response = self.session.get(
                url,
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
                "Could not establish a connection to TMDB. "
                f"Details: {exc}"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                "TMDB request timed out. Check your internet connection."
            ) from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"TMDB request failed: {exc}") from exc

        if response.status_code == 401:
            raise RuntimeError(
                "TMDB returned HTTP 401 Unauthorized. "
                "The token is not being accepted by TMDB. "
                "Use the TMDB API Read Access Token (Bearer token)."
            )
        if response.status_code == 403:
            raise RuntimeError(
                "TMDB returned HTTP 403 Forbidden."
            )
        if response.status_code == 429:
            raise RuntimeError(
                "TMDB rate limit reached. Please try again shortly."
            )
        if not response.ok:
            raise RuntimeError(
                f"TMDB returned HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError("TMDB returned an invalid JSON response.") from exc

    def test_connection(self):
        data = self._request("/configuration")
        if data.get("images") is None:
            raise RuntimeError("TMDB responded, but the configuration response was unexpected.")
        return "TMDB connection successful."

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
        return [self._normalize_movie(x) for x in data.get("results", [])[:max_results]]

    def get_movie(self, movie_id):
        data = self._request(f"/movie/{movie_id}", {"language": "en-US"})
        credits = self._request(f"/movie/{movie_id}/credits", {"language": "en-US"})
        director = next(
            (c.get("name") for c in credits.get("crew", []) if c.get("job") == "Director"),
            "",
        )
        cast = [c.get("name") for c in credits.get("cast", [])[:8] if c.get("name")]
        item = self._normalize_movie(data)
        item.update({
            "runtime": data.get("runtime"),
            "genres": [x.get("name") for x in data.get("genres", [])],
            "overview": data.get("overview", ""),
            "rating": data.get("vote_average"),
            "vote_count": data.get("vote_count"),
            "director": director,
            "cast": cast,
        })
        return item

    @staticmethod
    def _normalize_movie(item):
        poster = item.get("poster_path")
        backdrop = item.get("backdrop_path")
        image_base = "https://image.tmdb.org/t/p/w500"
        return {
            "id": item.get("id"),
            "title": item.get("title"),
            "original_title": item.get("original_title"),
            "year": item.get("release_date", "")[:4] if item.get("release_date") else "",
            "overview": item.get("overview", ""),
            "poster_path": poster,
            "backdrop_path": backdrop,
            "poster_url": image_base + poster if poster else "",
            "backdrop_url": image_base + backdrop if backdrop else "",
        }
