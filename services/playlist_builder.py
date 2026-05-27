import logging
from concurrent.futures import ThreadPoolExecutor

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
    ):
        self._setlistfm = setlistfm
        self._resolver  = resolver
        self._spotify   = spotify
        self._executor  = executor

    def build(
        self,
        artists: list[dict],
        prefer_original: bool,
        include_taped: bool,
        playlist_name: str,
    ) -> dict:
        all_track_ids, artist_results = self._collect_tracks(artists, prefer_original, include_taped)

        if not all_track_ids:
            return {"error": "no_tracks_found", "details": artist_results}

        user_id = self._spotify.get_current_user_id()
        playlist_id, playlist_url = self._spotify.create_playlist(user_id, playlist_name, _DESCRIPTION)
        failed_chunks = self._spotify.add_tracks(playlist_id, all_track_ids)

        log.info(
            "playlist created id=%s tracks=%d failed_chunks=%d",
            playlist_id, len(all_track_ids), failed_chunks,
        )

        return {
            "playlist_url":  playlist_url,
            "playlist_id":   playlist_id,
            "total_tracks":  len(all_track_ids),
            "failed_chunks": failed_chunks,
            "artists":       artist_results,
        }

    def _collect_tracks(
        self, artists: list[dict], prefer_original: bool, include_taped: bool
    ) -> tuple[list[str], list[dict]]:
        futures = [
            self._executor.submit(self._process_artist, a, prefer_original, include_taped)
            for a in artists
        ]
        all_track_ids, artist_results = [], []
        for future in futures:
            track_ids, result = future.result()
            artist_results.append(result)
            if track_ids:
                all_track_ids.extend(track_ids)
        return all_track_ids, artist_results

    def _process_artist(
        self, artist: dict, prefer_original: bool, include_taped: bool
    ) -> tuple[list[str], dict]:
        name = artist.get("name", "")
        mbid = artist.get("mbid")
        songs, err = self._setlistfm.get_recent_setlist(mbid, name, include_taped)

        if err in ("setlistfm_api_key_invalid", "setlistfm_rate_limited"):
            raise RuntimeError(err)

        if not songs:
            log.info("no setlist found for artist=%s err=%s", name, err)
            return [], {"name": name, "status": "no_setlist", "tracks": 0, "missing": []}

        track_ids, missing = self._resolver.resolve_all(name, songs, prefer_original)
        log.info(
            "artist=%s songs=%d resolved=%d missing=%d",
            name, len(songs), len(track_ids), len(missing),
        )
        return track_ids, {
            "name":    name,
            "status":  "ok" if track_ids else "no_tracks",
            "tracks":  len(track_ids),
            "missing": missing,
        }
