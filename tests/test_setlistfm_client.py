import pytest
import requests

import errors
from config import Config
from infrastructure.cache import TTLCache
from infrastructure.setlistfm_client import SetlistFMClient


def make_config(api_key="key"):
    return Config(
        spotify_client_id="id",
        spotify_client_secret="secret",
        spotify_refresh_token="token",
        setlistfm_api_key=api_key,
        setlistfm_rate_per_sec=1000.0,  # sin espera real en tests
    )


CONFIG = make_config()


class FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return self._json


class FakeSession:
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs.get("params", {})))
        if self.exc:
            raise self.exc
        return self.response


def make_client(response=None, exc=None, config=CONFIG):
    session = FakeSession(response, exc)
    return SetlistFMClient(config, session, TTLCache(ttl=60)), session


def artist_page(names, total, items_per_page=20):
    return {
        "artist": [{"mbid": f"mbid-{n}", "name": n} for n in names],
        "total": total,
        "itemsPerPage": items_per_page,
    }


# --- search_artists: paginación ---

def test_search_artists_reports_more_pages_available():
    client, _ = make_client(FakeResponse(json_data=artist_page(["A"], total=50)))
    artists, err, has_more = client.search_artists("a", page=1)
    assert err is None
    assert has_more is True
    assert artists[0]["name"] == "A"


def test_search_artists_last_page_has_no_more():
    """total=50, 20 por página: la página 3 cubre hasta el ítem 60."""
    client, _ = make_client(FakeResponse(json_data=artist_page(["A"], total=50)))
    _, _, has_more = client.search_artists("a", page=3)
    assert has_more is False


def test_search_artists_exact_page_boundary_has_no_more():
    client, _ = make_client(FakeResponse(json_data=artist_page(["A"], total=40)))
    _, _, has_more = client.search_artists("a", page=2)
    assert has_more is False


def test_search_artists_passes_page_to_api():
    client, session = make_client(FakeResponse(json_data=artist_page(["A"], total=1)))
    client.search_artists("tool", page=4)
    _, params = session.calls[0]
    assert params["artistName"] == "tool"
    assert params["p"] == 4


def test_search_artists_maps_missing_fields():
    client, _ = make_client(FakeResponse(json_data={"artist": [{"name": "Solo"}]}))
    artists, _, _ = client.search_artists("solo")
    assert artists[0] == {
        "id": "Solo", "mbid": None, "name": "Solo",
        "sortName": "", "disambiguation": "", "url": "", "image": None,
    }


# --- search_artists: errores ---

def test_search_artists_without_api_key():
    client, session = make_client(config=make_config(api_key=""))
    assert client.search_artists("x") == ([], errors.SETLISTFM_NOT_CONFIGURED, False)
    assert session.calls == []


def test_search_artists_404_is_empty_not_error():
    client, _ = make_client(FakeResponse(status_code=404))
    assert client.search_artists("x") == ([], None, False)


@pytest.mark.parametrize("status,expected", [
    (401, errors.SETLISTFM_API_KEY_INVALID),
    (403, errors.SETLISTFM_QUOTA_EXCEEDED),
    (429, errors.SETLISTFM_RATE_LIMITED),
    (500, errors.SETLISTFM_HTTP_PREFIX + "500"),
])
def test_search_artists_error_codes(status, expected):
    client, _ = make_client(FakeResponse(status_code=status))
    assert client.search_artists("x") == ([], expected, False)


@pytest.mark.parametrize("exc,expected", [
    (requests.Timeout(), errors.SETLISTFM_TIMEOUT),
    (requests.ConnectionError(), errors.SETLISTFM_CONNECTION_ERROR),
])
def test_search_artists_network_errors(exc, expected):
    client, _ = make_client(exc=exc)
    assert client.search_artists("x") == ([], expected, False)


# --- get_recent_setlist: 401 y 403 son distintos ---

def test_recent_setlist_401_is_bad_key():
    client, _ = make_client(FakeResponse(status_code=401))
    assert client.get_recent_setlist(None, "A", False) == (None, errors.SETLISTFM_API_KEY_INVALID)


def test_recent_setlist_403_is_quota_exceeded():
    client, _ = make_client(FakeResponse(status_code=403))
    assert client.get_recent_setlist(None, "A", False) == (None, errors.SETLISTFM_QUOTA_EXCEEDED)
