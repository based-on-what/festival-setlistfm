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

_DESCRIPTION = "Created by Festival SetlistFM Creator – https://github.com/based-on-what/festival-setlistfm"


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
        prefer_original: bool,
        include_taped: bool,
        playlist_name: str,
        request_id: str = "",
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> dict:
        all_track_ids, artist_results = self._collect_tracks(
            artists, prefer_original, include_taped, request_id, progress_cb
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
    ) -> tuple[list[str], list[dict]]:
        futures = [
            self._executor.submit(self._process_artist, a, prefer_original, include_taped, request_id)
            for a in artists
        ]
        # Shared deadline: artists that miss it get status "timeout" and the
        # playlist is built from whatever resolved, instead of letting gunicorn
        # kill the whole request after the playlist may already exist.
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

        if err in (errors.SETLISTFM_API_KEY_INVALID, errors.SETLISTFM_RATE_LIMITED):
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
