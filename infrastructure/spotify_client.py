import logging
import time
import threading
from typing import Optional

import requests

import errors
from config import Config, SPOTIFY_TOKEN_URL, SPOTIFY_API_BASE
from infrastructure.cache import TTLCache

log = logging.getLogger(__name__)

# Sentinel cached for "track not on Spotify" so known misses don't re-query.
_SEARCH_MISS = object()


class _TokenCache:
    def __init__(self, config: Config, session: requests.Session):
        self._config  = config
        self._session = session
        self._token: Optional[str] = None
        self._expiry  = 0.0
        self._lock    = threading.Lock()

    def get(self) -> str:
        with self._lock:
            if self._token and time.time() < self._expiry - 60:
                return self._token
            self._token = self._refresh()
            return self._token

    def _refresh(self) -> str:
        cfg = self._config
        if not cfg.spotify_client_id or not cfg.spotify_client_secret:
            raise RuntimeError(errors.SPOTIFY_NOT_CONFIGURED)
        if not cfg.spotify_refresh_token:
            raise RuntimeError(errors.SPOTIFY_REFRESH_TOKEN_MISSING)

        try:
            resp = self._session.post(
                SPOTIFY_TOKEN_URL,
                data={"grant_type": "refresh_token", "refresh_token": cfg.spotify_refresh_token},
                auth=(cfg.spotify_client_id, cfg.spotify_client_secret),
                timeout=10,
            )
        except requests.Timeout:
            raise RuntimeError(errors.SPOTIFY_AUTH_TIMEOUT)
        except requests.ConnectionError:
            raise RuntimeError(errors.SPOTIFY_AUTH_CONNECTION_ERROR)

        if resp.status_code == 400:
            raise RuntimeError(errors.SPOTIFY_REFRESH_TOKEN_INVALID)
        if resp.status_code == 401:
            raise RuntimeError(errors.SPOTIFY_CREDENTIALS_INVALID)
        if not resp.ok:
            raise RuntimeError(f"{errors.SPOTIFY_AUTH_HTTP_PREFIX}{resp.status_code}")

        data = resp.json()
        self._expiry = time.time() + data.get("expires_in", 3600)
        log.info("spotify token refreshed, expires_in=%ds", data.get("expires_in", 3600))
        return data["access_token"]


class SpotifyClient:
    def __init__(
        self,
        config: Config,
        session: requests.Session,
        auth_session: requests.Session,
        search_cache: TTLCache = None,
    ):
        self._session      = session
        self._token_cache  = _TokenCache(config, auth_session)
        self._search_cache = search_cache

    def auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token_cache.get()}"}

    @staticmethod
    def _sleep_retry_after(resp, cap: float = 2.0) -> None:
        try:
            delay = float(resp.headers.get("Retry-After", "1"))
        except ValueError:
            delay = 1.0
        time.sleep(min(max(delay, 0.0), cap))

    def search_track(self, artist_name: Optional[str], track_name: str) -> Optional[str]:
        cache_key = (artist_name, track_name)
        if self._search_cache is not None:
            cached = self._search_cache.get(cache_key)
            if cached is not None:
                return None if cached is _SEARCH_MISS else cached

        q = f'artist:"{artist_name}" track:"{track_name}"' if artist_name else f'track:"{track_name}"'
        params = {"q": q, "type": "track", "limit": 1}

        def do_get():
            return self._session.get(
                f"{SPOTIFY_API_BASE}/search",
                headers=self.auth_headers(),
                params=params,
                timeout=6,
            )

        try:
            r = do_get()
            if r.status_code == 429:
                self._sleep_retry_after(r)
                r = do_get()
        except (requests.Timeout, requests.ConnectionError):
            return None
        if not r.ok:
            return None

        items = r.json().get("tracks", {}).get("items", [])
        tid = items[0]["id"] if items else None
        # Only definitive answers (HTTP ok) are cached; transient errors above
        # return early so they don't poison the cache.
        if self._search_cache is not None:
            self._search_cache.set(cache_key, _SEARCH_MISS if tid is None else tid)
        return tid

    def get_current_user_id(self) -> str:
        try:
            me = self._session.get(f"{SPOTIFY_API_BASE}/me", headers=self.auth_headers(), timeout=8)
        except requests.RequestException:
            raise RuntimeError(errors.SPOTIFY_NETWORK_ERROR)
        if me.status_code == 401:
            raise RuntimeError(errors.SPOTIFY_TOKEN_EXPIRED)
        if not me.ok:
            raise RuntimeError(errors.SPOTIFY_COULD_NOT_GET_USER)
        return me.json()["id"]

    def create_playlist(self, user_id: str, name: str, description: str) -> tuple[str, str]:
        hdrs = {**self.auth_headers(), "Content-Type": "application/json"}
        try:
            pl = self._session.post(
                f"{SPOTIFY_API_BASE}/users/{user_id}/playlists",
                headers=hdrs,
                json={"name": name, "public": False, "description": description},
                timeout=10,
            )
        except requests.RequestException:
            raise RuntimeError(errors.SPOTIFY_NETWORK_ERROR)
        if not pl.ok:
            raise RuntimeError(errors.SPOTIFY_PLAYLIST_CREATION_FAILED)
        data = pl.json()
        return data["id"], data["external_urls"]["spotify"]

    def add_tracks(self, playlist_id: str, track_ids: list[str]) -> int:
        hdrs   = {**self.auth_headers(), "Content-Type": "application/json"}
        failed = 0
        for i in range(0, len(track_ids), 100):
            chunk = track_ids[i: i + 100]

            def do_post():
                return self._session.post(
                    f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks",
                    headers=hdrs,
                    json={"uris": [f"spotify:track:{tid}" for tid in chunk]},
                    timeout=10,
                )

            try:
                r = do_post()
                # Retry only on 429 (request definitely not applied); retrying
                # network errors could double-add the chunk.
                if r.status_code == 429:
                    self._sleep_retry_after(r)
                    r = do_post()
                if not r.ok:
                    failed += 1
            except requests.RequestException:
                failed += 1
        return failed
