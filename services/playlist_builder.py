import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Callable, Optional

import errors
from infrastructure.setlistfm_client import SetlistFMClient
from infrastructure.spotify_client import SpotifyClient
from services.track_resolver import TrackResolver

log = logging.getLogger(__name__)

_DESCRIPTION = "Created by Festival SetlistFM Creator – https://festival-setlistfm.up.railway.app/"


class PlaylistBuilder:
    def __init__(
        self,
        setlistfm: SetlistFMClient,
        resolver: TrackResolver,
        spotify: SpotifyClient,
        executor: ThreadPoolExecutor,
        build_deadline_seconds: float = 90.0,
    ):
        self._setlistfm = setlistfm
        self._resolver  = resolver
        self._spotify   = spotify
        self._executor  = executor
        self._deadline_seconds = build_deadline_seconds

    def build(
        self,
        artists: list[dict],
        prefer_original: bool = True,
        include_taped: bool = False,
        playlist_name: str = "",
        request_id: str = "",
        progress_cb: Optional[Callable[[int, int], None]] = None,
        per_artist_versions: Optional[list[bool]] = None,
    ) -> dict:
        all_track_ids, artist_results = self._collect_tracks(
            artists, prefer_original, include_taped, request_id, progress_cb, per_artist_versions
        )

        if not all_track_ids:
            return {"error": errors.NO_TRACKS_FOUND, "details": artist_results}

        # Dedupe across artists (shared covers / festival anthems), keeping
        # first-occurrence order.
        deduped = list(dict.fromkeys(all_track_ids))
        duplicates_removed = len(all_track_ids) - len(deduped)

        user_id = self._spotify.get_current_user_id()
        playlist_id, playlist_url = self._spotify.create_playlist(user_id, playlist_name, _DESCRIPTION)
        failed_chunks = self._spotify.add_tracks(playlist_id, deduped)

        log.info(
            "rid=%s playlist created id=%s tracks=%d dupes_removed=%d failed_chunks=%d",
            request_id, playlist_id, len(deduped), duplicates_removed, failed_chunks,
        )

        return {
            "playlist_url":       playlist_url,
            "playlist_id":        playlist_id,
            "total_tracks":       len(deduped),
            "duplicates_removed": duplicates_removed,
            "failed_chunks":      failed_chunks,
            "artists":            artist_results,
        }

    def _collect_tracks(
        self, artists: list[dict], prefer_original: bool, include_taped: bool,
        request_id: str = "",
        progress_cb: Optional[Callable[[int, int], None]] = None,
        per_artist_versions: Optional[list[bool]] = None,
    ) -> tuple[list[str], list[dict]]:
        
        # Si no se envía la lista de preferencias por artista, usamos la global para todos
        if per_artist_versions is None:
            per_artist_versions = [prefer_original] * len(artists)

        futures = [
            self._executor.submit(self._process_artist, a, is_orig, include_taped, request_id)
            for a, is_orig in zip(artists, per_artist_versions)
        ]
        
        # Shared deadline
        deadline = time.monotonic() + self._deadline_seconds
        all_track_ids, artist_results = [], []
        for i, (future, artist) in enumerate(zip(futures, artists)):
            remaining = deadline - time.monotonic()
            try:
                track_ids, result = future.result(timeout=max(0.0, remaining))
            except FutureTimeoutError:
                future.cancel()
                name = artist.get("name", "")
                log.warning("rid=%s artist=%s missed build deadline", request_id, name)
                track_ids = []
                result = {"name": name, "status": "timeout", "tracks": 0, "missing": []}
            artist_results.append(result)
            if track_ids:
                all_track_ids.extend(track_ids)
            if progress_cb:
                progress_cb(i + 1, len(artists))
        return all_track_ids, artist_results

    def _process_artist(
        self, artist: dict, prefer_original: bool, include_taped: bool,
        request_id: str = "",
    ) -> tuple[list[str], dict]:
        name = artist.get("name", "")
        mbid = artist.get("mbid")
        songs, err = self._setlistfm.get_recent_setlist(mbid, name, include_taped)

        if err in (
            errors.SETLISTFM_API_KEY_INVALID,
            errors.SETLISTFM_RATE_LIMITED,
            errors.SETLISTFM_QUOTA_EXCEEDED,
        ):
            raise RuntimeError(err)

        if not songs:
            log.info("rid=%s no setlist found for artist=%s err=%s", request_id, name, err)
            return [], {"name": name, "status": "no_setlist", "tracks": 0, "missing": []}

        track_ids, missing = self._resolver.resolve_all(name, songs, prefer_original)
        log.info(
            "rid=%s artist=%s songs=%d resolved=%d missing=%d",
            request_id, name, len(songs), len(track_ids), len(missing),
        )
        return track_ids, {
            "name":    name,
            "status":  "ok" if track_ids else "no_tracks",
            "tracks":  len(track_ids),
            "missing": missing,
        }