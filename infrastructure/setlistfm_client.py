import logging
import threading
import time
from typing import Optional

import requests

import errors
from config import Config, SETLISTFM_API_BASE
from infrastructure.cache import TTLCache

log = logging.getLogger(__name__)


class _Throttle:
    """Process-wide pacing: each acquire() reserves the next free slot so
    concurrent callers queue at `rate` requests/sec instead of bursting."""

    def __init__(self, rate: float):
        self._interval  = 1.0 / rate
        self._lock      = threading.Lock()
        self._next_free = 0.0

    def acquire(self) -> None:
        with self._lock:
            now  = time.monotonic()
            wait = max(0.0, self._next_free - now)
            self._next_free = max(now, self._next_free) + self._interval
        if wait > 0:
            time.sleep(wait)


class SetlistFMClient:
    def __init__(self, config: Config, session: requests.Session, cache: TTLCache):
        self._config   = config
        self._session  = session
        self._cache    = cache
        self._throttle = _Throttle(config.setlistfm_rate_per_sec)

    def _headers(self) -> dict:
        return {"x-api-key": self._config.setlistfm_api_key, "Accept": "application/json"}

    def search_artists(self, q: str, page: int = 1) -> tuple[list[dict], Optional[str], bool]:
        if not self._config.setlistfm_api_key:
            return [], errors.SETLISTFM_NOT_CONFIGURED, False

        self._throttle.acquire()
        try:
            resp = self._session.get(
                f"{SETLISTFM_API_BASE}/search/artists",
                headers=self._headers(),
                params={"artistName": q, "sort": "relevance", "p": page},
                timeout=6,
            )
        except requests.Timeout:
            return [], errors.SETLISTFM_TIMEOUT, False
        except requests.ConnectionError:
            return [], errors.SETLISTFM_CONNECTION_ERROR, False

        if resp.status_code == 401:
            return [], errors.SETLISTFM_API_KEY_INVALID, False
        if resp.status_code == 404:
            return [], None, False
        if resp.status_code == 429:
            return [], errors.SETLISTFM_RATE_LIMITED, False
        if not resp.ok:
            return [], f"{errors.SETLISTFM_HTTP_PREFIX}{resp.status_code}", False

        data = resp.json()
        artists = [
            {
                "id":             a.get("mbid", a.get("name")),
                "mbid":           a.get("mbid"),
                "name":           a.get("name", ""),
                "sortName":       a.get("sortName", ""),
                "disambiguation": a.get("disambiguation", ""),
                "url":            a.get("url", ""),
                "image":          None,
            }
            for a in data.get("artist", [])
        ]
        total          = data.get("total", 0)
        items_per_page = data.get("itemsPerPage", 20)
        has_more       = page * items_per_page < total
        return artists, None, has_more

    def get_recent_setlist(
        self, mbid: Optional[str], artist_name: str, include_taped: bool
    ) -> tuple[Optional[list], Optional[str]]:
        if not self._config.setlistfm_api_key:
            return None, errors.SETLISTFM_NOT_CONFIGURED

        cache_key = (mbid or artist_name, include_taped)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached, None

        if mbid:
            url, base_params = f"{SETLISTFM_API_BASE}/artist/{mbid}/setlists", {}
        else:
            url, base_params = f"{SETLISTFM_API_BASE}/search/setlists", {"artistName": artist_name}

        for page in range(1, 6):
            self._throttle.acquire()
            try:
                resp = self._session.get(
                    url, headers=self._headers(), params={**base_params, "p": page}, timeout=8
                )
            except requests.Timeout:
                return None, errors.SETLISTFM_TIMEOUT
            except requests.ConnectionError:
                return None, errors.SETLISTFM_CONNECTION_ERROR

            if resp.status_code in (401, 403):
                return None, errors.SETLISTFM_API_KEY_INVALID
            if resp.status_code == 429:
                return None, errors.SETLISTFM_RATE_LIMITED
            if resp.status_code == 404 or not resp.ok:
                return None, None

            setlists = resp.json().get("setlist", [])
            if not setlists:
                return None, None

            for setlist in setlists:
                songs = self._extract_songs(setlist, include_taped)
                if len(songs) >= 3:
                    self._cache.set(cache_key, songs)
                    return songs, None

        return None, None

    @staticmethod
    def _extract_songs(setlist: dict, include_taped: bool) -> list[dict]:
        songs = []
        for sset in setlist.get("sets", {}).get("set", []):
            for song in sset.get("song", []):
                name = song.get("name", "").strip()
                if not name:
                    continue
                is_tape = bool(song.get("tape", False))
                if is_tape and not include_taped:
                    continue
                cover_info = song.get("cover")
                songs.append({
                    "name":                name,
                    "cover_artist":        cover_info.get("name") if cover_info else None,
                    "is_medley_candidate": " / " in name,
                    "is_tape":             is_tape,
                })
        return songs
