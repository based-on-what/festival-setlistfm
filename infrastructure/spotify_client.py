import logging
import time
import threading
from typing import Optional

import requests

from config import Config, SPOTIFY_TOKEN_URL, SPOTIFY_API_BASE

log = logging.getLogger(__name__)


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
            raise RuntimeError("spotify_not_configured")
        if not cfg.spotify_refresh_token:
            raise RuntimeError("spotify_refresh_token_missing")

        try:
            resp = self._session.post(
                SPOTIFY_TOKEN_URL,
                data={"grant_type": "refresh_token", "refresh_token": cfg.spotify_refresh_token},
                auth=(cfg.spotify_client_id, cfg.spotify_client_secret),
                timeout=10,
            )
        except requests.Timeout:
            raise RuntimeError("spotify_auth_timeout")
        except requests.ConnectionError:
            raise RuntimeError("spotify_auth_connection_error")

        if resp.status_code == 400:
            raise RuntimeError("spotify_refresh_token_invalid")
        if resp.status_code == 401:
            raise RuntimeError("spotify_credentials_invalid")
        if not resp.ok:
            raise RuntimeError(f"spotify_auth_http_{resp.status_code}")

        data = resp.json()
        self._expiry = time.time() + data.get("expires_in", 3600)
        log.info("spotify token refreshed, expires_in=%ds", data.get("expires_in", 3600))
        return data["access_token"]


class SpotifyClient:
    def __init__(self, config: Config, session: requests.Session, auth_session: requests.Session):
        self._session     = session
        self._token_cache = _TokenCache(config, auth_session)

    def auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token_cache.get()}"}

    def search_track(self, artist_name: Optional[str], track_name: str) -> Optional[str]:
        q = f'artist:"{artist_name}" track:"{track_name}"' if artist_name else f'track:"{track_name}"'
        try:
            r = self._session.get(
                f"{SPOTIFY_API_BASE}/search",
                headers=self.auth_headers(),
                params={"q": q, "type": "track", "limit": 1},
                timeout=6,
            )
        except (requests.Timeout, requests.ConnectionError):
            return None
        if r.ok:
            items = r.json().get("tracks", {}).get("items", [])
            if items:
                return items[0]["id"]
        return None

    def get_current_user_id(self) -> str:
        try:
            me = self._session.get(f"{SPOTIFY_API_BASE}/me", headers=self.auth_headers(), timeout=8)
        except requests.RequestException:
            raise RuntimeError("spotify_network_error")
        if me.status_code == 401:
            raise RuntimeError("spotify_token_expired")
        if not me.ok:
            raise RuntimeError("spotify_could_not_get_user")
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
            raise RuntimeError("spotify_network_error")
        if not pl.ok:
            raise RuntimeError("spotify_playlist_creation_failed")
        data = pl.json()
        return data["id"], data["external_urls"]["spotify"]

    def add_tracks(self, playlist_id: str, track_ids: list[str]) -> int:
        hdrs   = {**self.auth_headers(), "Content-Type": "application/json"}
        failed = 0
        for i in range(0, len(track_ids), 100):
            chunk = track_ids[i: i + 100]
            try:
                r = self._session.post(
                    f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks",
                    headers=hdrs,
                    json={"uris": [f"spotify:track:{tid}" for tid in chunk]},
                    timeout=10,
                )
                if not r.ok:
                    failed += 1
            except requests.RequestException:
                failed += 1
        return failed
