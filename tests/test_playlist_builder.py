import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from services.playlist_builder import PlaylistBuilder


SONG = {"name": "Song", "cover_artist": None, "is_medley_candidate": False, "is_tape": False}


class FakeSetlistFM:
    """Returns one song per artist; sleeps per-artist to simulate slowness."""

    def __init__(self, delays=None):
        self.delays = delays or {}

    def get_recent_setlist(self, mbid, artist_name, include_taped):
        time.sleep(self.delays.get(artist_name, 0))
        return [SONG], None


class FakeResolver:
    def __init__(self, track_id_by_artist=None):
        self.track_id_by_artist = track_id_by_artist or {}

    def resolve_all(self, artist_name, songs, prefer_original):
        tid = self.track_id_by_artist.get(artist_name, f"id_{artist_name}")
        return [tid], []


class FakeSpotify:
    def __init__(self):
        self.added = None

    def get_current_user_id(self):
        return "user"

    def create_playlist(self, user_id, name, description):
        return "pl1", "https://open.spotify.com/playlist/pl1"

    def add_tracks(self, playlist_id, track_ids):
        self.added = track_ids
        return 0


@pytest.fixture
def executor():
    with ThreadPoolExecutor(max_workers=4) as ex:
        yield ex


def test_deadline_marks_slow_artist_timeout(executor):
    setlistfm = FakeSetlistFM(delays={"Slow": 2.0})
    spotify = FakeSpotify()
    builder = PlaylistBuilder(setlistfm, FakeResolver(), spotify, executor,
                              build_deadline_seconds=0.3)
    result = builder.build(
        [{"name": "Fast"}, {"name": "Slow"}],
        prefer_original=True, include_taped=False, playlist_name="X",
    )
    statuses = {a["name"]: a["status"] for a in result["artists"]}
    assert statuses == {"Fast": "ok", "Slow": "timeout"}
    assert result["total_tracks"] == 1
    assert spotify.added == ["id_Fast"]


def test_duplicate_tracks_removed_across_artists(executor):
    spotify = FakeSpotify()
    resolver = FakeResolver({"A": "shared", "B": "shared", "C": "unique"})
    builder = PlaylistBuilder(FakeSetlistFM(), resolver, spotify, executor)
    result = builder.build(
        [{"name": "A"}, {"name": "B"}, {"name": "C"}],
        prefer_original=True, include_taped=False, playlist_name="X",
    )
    assert result["total_tracks"] == 2
    assert result["duplicates_removed"] == 1
    assert spotify.added == ["shared", "unique"]


def test_progress_callback_invoked(executor):
    builder = PlaylistBuilder(FakeSetlistFM(), FakeResolver(), FakeSpotify(), executor)
    calls = []
    builder.build(
        [{"name": "A"}, {"name": "B"}],
        prefer_original=True, include_taped=False, playlist_name="X",
        progress_cb=lambda done, total: calls.append((done, total)),
    )
    assert calls == [(1, 2), (2, 2)]
