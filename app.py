import os
import time
import requests
from datetime import date
from functools import lru_cache
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

SPOTIPY_CLIENT_ID = os.environ.get("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.environ.get("SPOTIPY_CLIENT_SECRET")
SETLISTFM_API_KEY = os.environ.get("SETLISTFM_API_KEY")

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SETLISTFM_API_BASE = "https://api.setlist.fm/rest/1.0"

_access_token = None
_token_expiry = 0


def get_access_token():
    global _access_token, _token_expiry
    if _access_token and time.time() < _token_expiry - 60:
        return _access_token
    refresh_token = os.environ.get("SPOTIPY_REFRESH_TOKEN")
    if not refresh_token:
        raise RuntimeError("SPOTIPY_REFRESH_TOKEN not configured.")
    resp = requests.post(
        SPOTIFY_TOKEN_URL,
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        auth=(SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET),
    )
    resp.raise_for_status()
    data = resp.json()
    _access_token = data["access_token"]
    _token_expiry = time.time() + data.get("expires_in", 3600)
    return _access_token


def spotify_headers():
    return {"Authorization": f"Bearer {get_access_token()}"}


@app.route("/")
def index():
    return render_template("index.html")


# ── Search artists via setlist.fm ──────────────────────────────────────────────

@app.route("/api/search-artist")
def search_artist():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"artists": []})
    if not SETLISTFM_API_KEY:
        return jsonify({"error": "SETLISTFM_API_KEY not configured."}), 503

    try:
        resp = requests.get(
            f"{SETLISTFM_API_BASE}/search/artists",
            headers={"x-api-key": SETLISTFM_API_KEY, "Accept": "application/json"},
            params={"artistName": q, "sort": "relevance", "p": 1},
            timeout=5,
        )
        resp.raise_for_status()
    except requests.HTTPError:
        return jsonify({"error": "setlistfm_error"}), 502
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503

    items = resp.json().get("artist", [])
    artists = []
    for a in items[:8]:
        artists.append({
            "id": a.get("mbid", a.get("name")),   # use mbid as unique id
            "mbid": a.get("mbid"),
            "name": a.get("name", ""),
            "sortName": a.get("sortName", ""),
            "disambiguation": a.get("disambiguation", ""),
            "url": a.get("url", ""),
            "image": None,                          # setlist.fm doesn't provide images
        })
    return jsonify({"artists": artists})


# ── Setlist helpers ────────────────────────────────────────────────────────────

def _extract_songs(setlist, include_taped):
    """
    Returns a list of dicts:
      { name, cover_artist, is_medley, is_tape }
    cover_artist is None when the song belongs to the performing artist.
    """
    songs = []
    for sset in setlist.get("sets", {}).get("set", []):
        for song in sset.get("song", []):
            name = song.get("name", "").strip()
            if not name:
                continue
            is_tape = bool(song.get("tape", False))
            if is_tape and not include_taped:
                continue
            cover_info = song.get("cover")          # {"mbid":…, "name":…} or None
            cover_artist = cover_info.get("name") if cover_info else None
            is_medley = bool(song.get("medley", False))
            songs.append({
                "name": name,
                "cover_artist": cover_artist,       # None → original artist's song
                "is_medley": is_medley,
                "is_tape": is_tape,
            })
    return songs


def _get_recent_setlist(mbid, artist_name, include_taped):
    """Fetch the most recent setlist with ≥3 songs for the given artist."""
    if not SETLISTFM_API_KEY:
        raise RuntimeError("SETLISTFM_API_KEY not configured.")
    headers = {"x-api-key": SETLISTFM_API_KEY, "Accept": "application/json"}

    if mbid:
        url = f"{SETLISTFM_API_BASE}/artist/{mbid}/setlists"
        base_params = {}
    else:
        url = f"{SETLISTFM_API_BASE}/search/setlists"
        base_params = {"artistName": artist_name}

    for page in range(1, 6):
        params = {**base_params, "p": page}
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code in (401, 403):
            raise RuntimeError("SETLISTFM_API_KEY is invalid or unauthorized.")
        if not resp.ok:
            return None
        setlists = resp.json().get("setlist", [])
        if not setlists:
            return None
        for setlist in setlists:
            songs = _extract_songs(setlist, include_taped)
            if len(songs) >= 3:
                return songs
    return None


# ── Spotify track resolution ───────────────────────────────────────────────────

def _search_spotify_track(hdrs, artist_name, track_name):
    """Search Spotify for a specific artist + track. Returns track_id or None."""
    r = requests.get(
        f"{SPOTIFY_API_BASE}/search",
        headers=hdrs,
        params={"q": f'artist:"{artist_name}" track:"{track_name}"', "type": "track", "limit": 1},
    )
    if r.ok:
        items = r.json().get("tracks", {}).get("items", [])
        if items:
            return items[0]["id"]
    return None


def _search_spotify_track_any_artist(hdrs, track_name):
    """Search Spotify for a track without restricting artist (for originals). Returns track_id or None."""
    r = requests.get(
        f"{SPOTIFY_API_BASE}/search",
        headers=hdrs,
        params={"q": f'track:"{track_name}"', "type": "track", "limit": 1},
    )
    if r.ok:
        items = r.json().get("tracks", {}).get("items", [])
        if items:
            return items[0]["id"]
    return None


def _resolve_track(hdrs, performing_artist, song, prefer_original):
    """
    Resolve a single song dict to a Spotify track ID.

    Logic:
    - Medley songs: always search by original artist (cover_artist if set, else performing_artist)
    - prefer_original=True:
        * If song has a cover_artist → search original artist first, fallback to performing_artist cover
        * If no cover_artist → search performing_artist
    - prefer_original=False:
        * Always search performing_artist (the cover version)
        * If not found, fallback to original artist (cover_artist) or any artist
    """
    name = song["name"]
    cover_artist = song["cover_artist"]   # None if it's the artist's own song
    is_medley = song["is_medley"]

    if is_medley:
        # For medleys, prefer the original recording
        original_artist = cover_artist or performing_artist
        tid = _search_spotify_track(hdrs, original_artist, name)
        if not tid:
            tid = _search_spotify_track_any_artist(hdrs, name)
        return tid

    if prefer_original:
        if cover_artist:
            # It's a cover → try original artist first
            tid = _search_spotify_track(hdrs, cover_artist, name)
            if tid:
                return tid
            # Fallback: the performing artist's cover
            return _search_spotify_track(hdrs, performing_artist, name)
        else:
            # Own song → search by performing artist
            return _search_spotify_track(hdrs, performing_artist, name)
    else:
        # prefer_original=False → want the cover (performing artist's version)
        tid = _search_spotify_track(hdrs, performing_artist, name)
        if tid:
            return tid
        # Fallback: original artist or any
        if cover_artist:
            tid = _search_spotify_track(hdrs, cover_artist, name)
        if not tid:
            tid = _search_spotify_track_any_artist(hdrs, name)
        return tid


def _collect_tracks(artists, hdrs, prefer_original, include_taped):
    all_track_ids = []
    artist_results = []
    for artist in artists:
        name = artist.get("name", "")
        mbid = artist.get("mbid")
        songs = _get_recent_setlist(mbid, name, include_taped)
        if not songs:
            artist_results.append({"name": name, "status": "no_setlist", "tracks": 0})
            continue
        track_ids = []
        for song in songs:
            tid = _resolve_track(hdrs, name, song, prefer_original)
            if tid:
                track_ids.append(tid)
        all_track_ids.extend(track_ids)
        artist_results.append({"name": name, "status": "ok", "tracks": len(track_ids)})
    return all_track_ids, artist_results


# ── Create playlist endpoint ───────────────────────────────────────────────────

@app.route("/api/create-playlist", methods=["POST"])
def create_playlist():
    body = request.get_json()
    artists = body.get("artists", [])
    if not artists:
        return jsonify({"error": "no_artists"}), 400

    prefer_original = bool(body.get("prefer_original", True))
    include_taped = bool(body.get("include_taped", False))

    try:
        hdrs = spotify_headers()
        all_track_ids, artist_results = _collect_tracks(
            artists, hdrs, prefer_original, include_taped
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    if not all_track_ids:
        return jsonify({"error": "no_tracks_found", "details": artist_results}), 400

    me = requests.get(f"{SPOTIFY_API_BASE}/me", headers=hdrs)
    if not me.ok:
        return jsonify({"error": "could_not_get_user"}), 502
    user_id = me.json()["id"]

    today = date.today().strftime("%Y-%m-%d")
    pl = requests.post(
        f"{SPOTIFY_API_BASE}/users/{user_id}/playlists",
        headers={**hdrs, "Content-Type": "application/json"},
        json={
            "name": f"Festival Setlist – {today}",
            "public": False,
            "description": "Created by Festival SetlistFM Creator, an open source project in GitHub: https://github.com/based-on-what/festival-setlistfm",
        },
    )
    if not pl.ok:
        return jsonify({"error": "playlist_creation_failed"}), 502

    playlist_id = pl.json()["id"]
    playlist_url = pl.json()["external_urls"]["spotify"]

    for i in range(0, len(all_track_ids), 100):
        chunk = all_track_ids[i: i + 100]
        requests.post(
            f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks",
            headers={**hdrs, "Content-Type": "application/json"},
            json={"uris": [f"spotify:track:{tid}" for tid in chunk]},
        )

    return jsonify({
        "playlist_url": playlist_url,
        "playlist_id": playlist_id,
        "total_tracks": len(all_track_ids),
        "artists": artist_results,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=False)