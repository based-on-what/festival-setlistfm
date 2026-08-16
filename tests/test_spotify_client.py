import time

import pytest

from config import Config
from infrastructure.cache import TTLCache
from infrastructure.spotify_client import SpotifyClient


CONFIG = Config(
    spotify_client_id="id",
    spotify_client_secret="secret",
    spotify_refresh_token="token",
    setlistfm_api_key="key",
)


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.headers = headers or {}

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return self._json


def track_payload(track_id, artist="Artist"):
    items = [{"id": track_id, "artists": [{"name": artist}]}] if track_id else []
    return {"tracks": {"items": items}}


def multi_track_payload(*pairs):
    """pairs: (track_id, artist_name) en el orden que los devuelve Spotify."""
    return {"tracks": {"items": [{"id": tid, "artists": [{"name": a}]} for tid, a in pairs]}}


class FakeSession:
    """Returns queued responses for get/post, records call count."""

    def __init__(self, get_responses=None, post_responses=None):
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.get_calls = 0
        self.post_calls = 0

    def get(self, *args, **kwargs):
        self.get_calls += 1
        return self.get_responses.pop(0)

    def post(self, *args, **kwargs):
        self.post_calls += 1
        if self.post_responses:
            return self.post_responses.pop(0)
        # auth token refresh path
        return FakeResponse(json_data={"access_token": "at", "expires_in": 3600})


def make_client(get_responses=None, post_responses=None, cache=None):
    session = FakeSession(get_responses, post_responses)
    auth_session = FakeSession()
    return SpotifyClient(CONFIG, session, auth_session, cache), session


def test_search_track_hit_is_cached():
    cache = TTLCache(ttl=60)
    client, session = make_client([FakeResponse(json_data=track_payload("t1"))], cache=cache)
    assert client.search_track("Artist", "Song") == "t1"
    assert client.search_track("Artist", "Song") == "t1"
    assert session.get_calls == 1


def test_search_track_miss_is_cached():
    cache = TTLCache(ttl=60)
    client, session = make_client([FakeResponse(json_data=track_payload(None))], cache=cache)
    assert client.search_track("Artist", "Nope") is None
    assert client.search_track("Artist", "Nope") is None
    assert session.get_calls == 1


def test_search_track_error_not_cached():
    cache = TTLCache(ttl=60)
    responses = [FakeResponse(status_code=500), FakeResponse(json_data=track_payload("t1"))]
    client, session = make_client(responses, cache=cache)
    assert client.search_track("Artist", "Song") is None
    assert client.search_track("Artist", "Song") == "t1"
    assert session.get_calls == 2


def test_search_track_retries_on_429(monkeypatch):
    sleeps = []
    monkeypatch.setattr(time, "sleep", sleeps.append)
    responses = [
        FakeResponse(status_code=429, headers={"Retry-After": "1"}),
        FakeResponse(json_data=track_payload("t1")),
    ]
    client, session = make_client(responses)
    assert client.search_track("Artist", "Song") == "t1"
    assert session.get_calls == 2
    assert sleeps == [1.0]


def test_search_track_429_twice_gives_none(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)
    responses = [FakeResponse(status_code=429), FakeResponse(status_code=429)]
    client, session = make_client(responses)
    assert client.search_track("Artist", "Song") is None
    assert session.get_calls == 2


def test_retry_after_capped_at_2s(monkeypatch):
    sleeps = []
    monkeypatch.setattr(time, "sleep", sleeps.append)
    responses = [
        FakeResponse(status_code=429, headers={"Retry-After": "30"}),
        FakeResponse(json_data=track_payload("t1")),
    ]
    client, _ = make_client(responses)
    client.search_track("Artist", "Song")
    assert sleeps == [2.0]


def test_search_track_skips_wrong_artist():
    """Spotify devuelve un track de otro intérprete: no debe aceptarse."""
    payload = multi_track_payload(("wrong", "Otra Banda"), ("right", "Artist"))
    client, _ = make_client([FakeResponse(json_data=payload)])
    assert client.search_track("Artist", "Song") == "right"


def test_search_track_no_artist_match_is_none():
    payload = multi_track_payload(("wrong", "Otra Banda"))
    client, _ = make_client([FakeResponse(json_data=payload)])
    assert client.search_track("Artist", "Song") is None


def test_search_track_matches_artist_leniently():
    """'The Beatles' debe casar con 'Beatles' y viceversa."""
    payload = multi_track_payload(("t1", "The Beatles"))
    client, _ = make_client([FakeResponse(json_data=payload)])
    assert client.search_track("Beatles", "Song") == "t1"


def test_search_track_ignores_accents_and_punctuation():
    payload = multi_track_payload(("t1", "Héroes del Silencio"))
    client, _ = make_client([FakeResponse(json_data=payload)])
    assert client.search_track("Heroes del Silencio", "Song") == "t1"


def test_search_track_prefers_exact_artist_over_lenient():
    """El match exacto gana aunque aparezca después en los resultados."""
    payload = multi_track_payload(("lenient", "Artist Tribute Band"), ("exact", "Artist"))
    client, _ = make_client([FakeResponse(json_data=payload)])
    assert client.search_track("Artist", "Song") == "exact"


def test_search_track_without_artist_takes_first_item():
    """Fallback de medley: sin artista se acepta el primer resultado tal cual."""
    payload = multi_track_payload(("t1", "Cualquiera"))
    client, _ = make_client([FakeResponse(json_data=payload)])
    assert client.search_track(None, "Song") == "t1"


def test_add_tracks_retries_chunk_on_429(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)
    # Main session posts: first 429, then 201. Token refresh goes to auth_session.
    session = FakeSession(post_responses=[FakeResponse(status_code=429), FakeResponse(status_code=201)])
    auth_session = FakeSession()
    client = SpotifyClient(CONFIG, session, auth_session)
    failed = client.add_tracks("pl1", ["t1"])
    assert failed == 0
    assert session.post_calls == 2


def test_add_tracks_counts_failed_chunk():
    session = FakeSession(post_responses=[FakeResponse(status_code=500)])
    client = SpotifyClient(CONFIG, session, FakeSession())
    assert client.add_tracks("pl1", ["t1"]) == 1
