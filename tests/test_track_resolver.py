from concurrent.futures import ThreadPoolExecutor

import pytest

from services.track_resolver import TrackResolver


class StubSpotify:
    """search_track stub: maps (artist, track) -> track_id, records calls."""

    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def search_track(self, artist_name, track_name):
        self.calls.append((artist_name, track_name))
        return self.mapping.get((artist_name, track_name))


def song(name, cover_artist=None):
    return {
        "name": name,
        "cover_artist": cover_artist,
        "is_medley_candidate": " / " in name,
        "is_tape": False,
    }


@pytest.fixture
def executor():
    with ThreadPoolExecutor(max_workers=2) as ex:
        yield ex


def make_resolver(mapping, executor):
    spotify = StubSpotify(mapping)
    return TrackResolver(spotify, executor), spotify


def test_plain_song_resolved_by_performer(executor):
    resolver, spotify = make_resolver({("Artist", "Song"): "t1"}, executor)
    ids = resolver._resolve_song("Artist", song("Song"), prefer_original=True)
    assert ids == ["t1"]
    assert spotify.calls == [("Artist", "Song")]


def test_cover_prefer_original_searches_cover_artist_first(executor):
    resolver, spotify = make_resolver({("Original", "Hit"): "t1"}, executor)
    ids = resolver._resolve_song("Performer", song("Hit", cover_artist="Original"), True)
    assert ids == ["t1"]
    assert spotify.calls[0] == ("Original", "Hit")


def test_cover_prefer_original_falls_back_to_performer(executor):
    resolver, spotify = make_resolver({("Performer", "Hit"): "t2"}, executor)
    ids = resolver._resolve_song("Performer", song("Hit", cover_artist="Original"), True)
    assert ids == ["t2"]
    assert spotify.calls == [("Original", "Hit"), ("Performer", "Hit")]


def test_cover_no_prefer_original_searches_performer_first(executor):
    resolver, spotify = make_resolver({("Performer", "Hit"): "t1"}, executor)
    ids = resolver._resolve_song("Performer", song("Hit", cover_artist="Original"), False)
    assert ids == ["t1"]
    assert spotify.calls[0] == ("Performer", "Hit")


def test_cover_no_prefer_original_fallback_is_cover_artist(executor):
    resolver, spotify = make_resolver({("Original", "Hit"): "t3"}, executor)
    ids = resolver._resolve_song("Performer", song("Hit", cover_artist="Original"), False)
    assert ids == ["t3"]
    assert spotify.calls == [("Performer", "Hit"), ("Original", "Hit")]


def test_medley_split_resolves_parts(executor):
    mapping = {("Artist", "Part One"): "p1", ("Artist", "Part Two"): "p2"}
    resolver, _ = make_resolver(mapping, executor)
    ids = resolver._resolve_song("Artist", song("Part One / Part Two"), True)
    assert ids == ["p1", "p2"]


def test_medley_part_last_resort_without_artist(executor):
    mapping = {(None, "Obscure"): "p9"}
    resolver, spotify = make_resolver(mapping, executor)
    ids = resolver._resolve_song("Artist", song("Obscure / Missing"), True)
    assert ids == ["p9"]
    assert (None, "Obscure") in spotify.calls


def test_no_match_returns_empty(executor):
    resolver, _ = make_resolver({}, executor)
    assert resolver._resolve_song("Artist", song("Nothing"), True) == []


def test_resolve_all_order_and_missing(executor):
    mapping = {("Artist", "A"): "ta", ("Artist", "C"): "tc"}
    resolver, _ = make_resolver(mapping, executor)
    songs = [song("A"), song("B"), song("C")]
    track_ids, missing = resolver.resolve_all("Artist", songs, prefer_original=True)
    assert track_ids == ["ta", "tc"]
    assert missing == ["B"]


def test_resolve_all_swallows_exceptions(executor):
    class BoomSpotify:
        def search_track(self, artist_name, track_name):
            raise ValueError("boom")

    resolver = TrackResolver(BoomSpotify(), executor)
    track_ids, missing = resolver.resolve_all("Artist", [song("X")], True)
    assert track_ids == []
    assert missing == ["X"]
