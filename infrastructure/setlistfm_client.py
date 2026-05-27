import logging
from typing import Optional

import requests

from config import Config, SETLISTFM_API_BASE
from infrastructure.cache import TTLCache

log = logging.getLogger(__name__)


class SetlistFMClient:
    def __init__(self, config: Config, session: requests.Session, cache: TTLCache):
        self._config  = config
        self._session = session
        self._cache   = cache

    def _headers(self) -> dict:
        return {"x-api-key": self._config.setlistfm_api_key, "Accept": "application/json"}

    def search_artists(self, q: str) -> tuple[list[dict], Optional[str]]:
        if not self._config.setlistfm_api_key:
            return [], "setlistfm_not_configured"

        try:
            resp = self._session.get(
                f"{SETLISTFM_API_BASE}/search/artists",
                headers=self._headers(),
                params={"artistName": q, "sort": "relevance", "p": 1},
                timeout=6,
            )
        except requests.Timeout:
            return [], "setlistfm_timeout"
        except requests.ConnectionError:
            return [], "setlistfm_connection_error"

        if resp.status_code == 401:
            return [], "setlistfm_api_key_invalid"
        if resp.status_code == 404:
            return [], None
        if resp.status_code == 429:
            return [], "setlistfm_rate_limited"
        if not resp.ok:
            return [], f"setlistfm_http_{resp.status_code}"

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
            for a in resp.json().get("artist", [])[:8]
        ]
        return artists, None

    def get_recent_setlist(
        self, mbid: Optional[str], artist_name: str, include_taped: bool
    ) -> tuple[Optional[list], Optional[str]]:
        if not self._config.setlistfm_api_key:
            return None, "setlistfm_not_configured"

        cache_key = (mbid or artist_name, include_taped)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached, None

        if mbid:
            url, base_params = f"{SETLISTFM_API_BASE}/artist/{mbid}/setlists", {}
        else:
            url, base_params = f"{SETLISTFM_API_BASE}/search/setlists", {"artistName": artist_name}

        for page in range(1, 6):
            try:
                resp = self._session.get(
                    url, headers=self._headers(), params={**base_params, "p": page}, timeout=8
                )
            except requests.Timeout:
                return None, "setlistfm_timeout"
            except requests.ConnectionError:
                return None, "setlistfm_connection_error"

            if resp.status_code in (401, 403):
                return None, "setlistfm_api_key_invalid"
            if resp.status_code == 429:
                return None, "setlistfm_rate_limited"
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
