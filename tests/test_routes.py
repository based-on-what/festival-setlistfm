import time

import pytest

from app import create_app
from config import Config


TEST_CONFIG = Config(
    spotify_client_id="id",
    spotify_client_secret="secret",
    spotify_refresh_token="token",
    setlistfm_api_key="key",
)


class FakeSetlistFM:
    def __init__(self, artists=None, error=None):
        self.artists = artists or []
        self.error = error

    def search_artists(self, q, page=1):
        return self.artists, self.error, False


class FakeBuilder:
    def __init__(self, result=None, exc=None):
        self.result = result
        self.exc = exc
        self.last_call = None

    def build(self, artists, prefer_original, include_taped, playlist_name,
              request_id="", progress_cb=None):
        self.last_call = (artists, prefer_original, include_taped, playlist_name)
        if self.exc:
            raise self.exc
        return self.result


def make_client(setlistfm=None, builder=None):
    app = create_app(
        TEST_CONFIG,
        setlistfm=setlistfm or FakeSetlistFM(),
        builder=builder or FakeBuilder(result={}),
    )
    app.config["TESTING"] = True
    return app.test_client()


# --- GET /api/search-artist ---

def test_search_empty_query_returns_empty_list():
    client = make_client()
    resp = client.get("/api/search-artist?q=")
    assert resp.status_code == 200
    assert resp.get_json() == {"artists": [], "has_more": False}


def test_search_returns_artists():
    artists = [{"id": "m1", "mbid": "m1", "name": "Tool"}]
    client = make_client(setlistfm=FakeSetlistFM(artists=artists))
    resp = client.get("/api/search-artist?q=tool")
    assert resp.status_code == 200
    assert resp.get_json() == {"artists": artists, "has_more": False}


@pytest.mark.parametrize("error,status", [
    ("setlistfm_not_configured", 503),
    ("setlistfm_rate_limited", 429),
    ("setlistfm_quota_exceeded", 429),
    ("setlistfm_timeout", 504),
    ("setlistfm_connection_error", 502),
    ("setlistfm_http_500", 502),
])
def test_search_error_mapping(error, status):
    client = make_client(setlistfm=FakeSetlistFM(error=error))
    resp = client.get("/api/search-artist?q=x")
    assert resp.status_code == status
    assert resp.get_json() == {"error": error}


# --- POST /api/create-playlist ---

def post_playlist(client, body):
    return client.post("/api/create-playlist", json=body)


def run_job(client, body, timeout=5.0):
    """POST, then poll the status endpoint until the job reaches a terminal state."""
    resp = post_playlist(client, body)
    assert resp.status_code == 202, resp.get_json()
    job_id = resp.get_json()["job_id"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get(f"/api/playlist-status/{job_id}").get_json()
        if status["state"] in ("done", "error"):
            return status
        time.sleep(0.02)
    raise AssertionError("job did not finish in time")


def test_create_playlist_no_artists():
    resp = post_playlist(make_client(), {"artists": []})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "no_artists"}


def test_create_playlist_too_many_artists():
    artists = [{"name": f"A{i}"} for i in range(TEST_CONFIG.max_artists + 1)]
    resp = post_playlist(make_client(), {"artists": artists})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "too_many_artists"}


def test_create_playlist_filters_invalid_entries():
    resp = post_playlist(make_client(), {"artists": ["junk", {"name": "  "}]})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "no_artists"}


def test_create_playlist_success():
    result = {
        "playlist_url": "https://open.spotify.com/playlist/x",
        "playlist_id": "x",
        "total_tracks": 5,
        "duplicates_removed": 0,
        "failed_chunks": 0,
        "artists": [{"name": "Tool", "status": "ok", "tracks": 5, "missing": []}],
    }
    builder = FakeBuilder(result=result)
    client = make_client(builder=builder)
    status = run_job(client, {
        "artists": [{"id": "m1", "mbid": "m1", "name": "Tool"}],
        "prefer_original": False,
        "include_taped": True,
        "playlist_name": "My Fest",
    })
    assert status["state"] == "done"
    assert status["result"] == result
    artists, prefer_original, include_taped, playlist_name = builder.last_call
    assert prefer_original is False
    assert include_taped is True
    assert playlist_name == "My Fest"


def test_create_playlist_default_name_when_blank():
    builder = FakeBuilder(result={"playlist_url": "u", "playlist_id": "i",
                                  "total_tracks": 1, "failed_chunks": 0, "artists": []})
    client = make_client(builder=builder)
    status = run_job(client, {"artists": [{"name": "Tool"}], "playlist_name": "   "})
    assert status["state"] == "done"
    assert builder.last_call[3].startswith("Festival Setlist – ")


def test_create_playlist_runtime_error_sets_job_error():
    builder = FakeBuilder(exc=RuntimeError("setlistfm_rate_limited"))
    status = run_job(make_client(builder=builder), {"artists": [{"name": "Tool"}]})
    assert status["state"] == "error"
    assert status["error"] == "setlistfm_rate_limited"


def test_create_playlist_no_tracks_found_sets_job_error():
    builder = FakeBuilder(result={"error": "no_tracks_found", "details": []})
    status = run_job(make_client(builder=builder), {"artists": [{"name": "Tool"}]})
    assert status["state"] == "error"
    assert status["error"] == "no_tracks_found"
    assert status["result"]["details"] == []


def test_playlist_status_unknown_job_404():
    resp = make_client().get("/api/playlist-status/deadbeef")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "job_not_found"}
