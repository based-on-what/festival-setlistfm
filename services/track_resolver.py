import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from infrastructure.spotify_client import SpotifyClient

log = logging.getLogger(__name__)


class TrackResolver:
    def __init__(self, spotify: SpotifyClient, executor: ThreadPoolExecutor):
        self._spotify  = spotify
        self._executor = executor

    def resolve_all(
        self, artist_name: str, songs: list[dict], prefer_original: bool
    ) -> tuple[list[str], list[str]]:
        futures = {
            i: self._executor.submit(self._resolve_song, artist_name, song, prefer_original)
            for i, song in enumerate(songs)
        }
        track_ids, missing = [], []
        for i in range(len(songs)):
            try:
                ids = futures[i].result()
            except Exception:
                ids = []
            if ids:
                track_ids.extend(ids)
            else:
                missing.append(songs[i]["name"])
        return track_ids, missing

    def _resolve_song(self, artist_name: str, song: dict, prefer_original: bool) -> list[str]:
        name         = song["name"]
        cover_artist = song["cover_artist"]

        tid = self._resolve_with_fallback(artist_name, cover_artist, name, prefer_original)
        if tid:
            return [tid]

        if song["is_medley_candidate"]:
            results = []
            for part in (p.strip() for p in name.split(" / ") if p.strip()):
                t = self._resolve_with_fallback(artist_name, cover_artist, part, prefer_original)
                if not t:
                    t = self._spotify.search_track(None, part)
                if t:
                    results.append(t)
            return results

        return []

    def _resolve_with_fallback(
        self,
        performing_artist: str,
        cover_artist: Optional[str],
        track_name: str,
        prefer_original: bool,
    ) -> Optional[str]:
        primary  = cover_artist if (prefer_original and cover_artist) else performing_artist
        fallback = performing_artist if (prefer_original and cover_artist) else cover_artist

        tid = self._spotify.search_track(primary, track_name)
        if not tid and fallback:
            tid = self._spotify.search_track(fallback, track_name)
        return tid
