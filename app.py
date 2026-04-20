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
MUSICBRAINZ_API = "https://musicbrainz.org/ws/2/artist/"
MB_HEADERS = {"User-Agent": "FestivalSetlistCreator/1.0 (festival-setlistfm.up.railway.app)"}

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


@lru_cache(maxsize=512)
def _lookup_artist_metadata(artist_name):
    try:
        resp = requests.get(
            MUSICBRAINZ_API,
            headers=MB_HEADERS,
            params={"query": f'artist:"{artist_name}"', "fmt": "json", "limit": 5},
            timeout=1.8,
        )
        if not resp.ok:
            return None, [], None
        candidates = resp.json().get("artists", [])
        if not candidates:
            return None, [], None
        match = next(
            (a for a in candidates if a.get("name", "").lower() == artist_name.lower()),
            candidates[0],
        )
        mbid = match.get("id")
        country = (
            (match.get("area") or {}).get("name")
            or (match.get("begin-area") or {}).get("name")
            or match.get("country")
        )
        tags = match.get("genres") or match.get("tags") or []
        genres = [t["name"] for t in sorted(tags, key=lambda x: x.get("count", 0), reverse=True)][:3]
        return country, genres, mbid
    except Exception:
        return None, [], None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search-artist")
def search_artist():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"artists": []})
    try:
        resp = requests.get(
            f"{SPOTIFY_API_BASE}/search",
            headers=spotify_headers(),
            params={"q": q, "type": "artist", "limit": 8},
        )
        resp.raise_for_status()
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except requests.HTTPError:
        return jsonify({"error": "spotify_error"}), 502
    items = resp.json().get("artists", {}).get("items", [])
    artists = []
    for a in items:
        country, mb_genres, mbid = _lookup_artist_metadata(a["name"])
        genres = mb_genres or a.get("genres", [])[:3]
        artists.append({
            "id": a["id"],
            "name": a["name"],
            "image": a["images"][-1]["url"] if a.get("images") else None,
            "genres": genres,
            "country": country,
            "mbid": mbid,
        })
    return jsonify({"artists": artists})


def _extract_songs(setlist):
    return [
        song.get("name", "").strip()
        for sset in setlist.get("sets", {}).get("set", [])
        for song in sset.get("song", [])
        if song.get("name", "").strip() and not song.get("tape", False)
    ]


def _get_recent_setlist(artist_name, mbid=None):
    if not SETLISTFM_API_KEY:
        raise RuntimeError("SETLISTFM_API_KEY not configured.")
    headers = {"x-api-key": SETLISTFM_API_KEY, "Accept": "application/json"}

    if mbid:
        url = f"{SETLISTFM_API_BASE}/artist/{mbid}/setlists"
    else:
        url = f"{SETLISTFM_API_BASE}/search/setlists"

    for page in range(1, 6):
        params = {"p": page} if mbid else {"artistName": artist_name, "p": page}
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code in (401, 403):
            raise RuntimeError("SETLISTFM_API_KEY is invalid or unauthorized.")
        if not resp.ok:
            return None
        setlists = resp.json().get("setlist", [])
        if not setlists:
            return None
        for setlist in setlists:
            songs = _extract_songs(setlist)
            if len(songs) >= 3:
                return songs
    return None


def _find_track_ids(artist_name, songs, hdrs):
    track_ids = []
    for song in songs:
        r = requests.get(
            f"{SPOTIFY_API_BASE}/search",
            headers=hdrs,
            params={"q": f"artist:{artist_name} track:{song}", "type": "track", "limit": 1},
        )
        if r.ok:
            items = r.json().get("tracks", {}).get("items", [])
            if items:
                track_ids.append(items[0]["id"])
    return track_ids


def _collect_tracks(artists, hdrs):
    all_track_ids = []
    artist_results = []
    for artist in artists:
        name = artist.get("name", "")
        mbid = artist.get("mbid")
        songs = _get_recent_setlist(name, mbid=mbid)
        if not songs:
            artist_results.append({"name": name, "status": "no_setlist", "tracks": 0})
            continue
        track_ids = _find_track_ids(name, songs, hdrs)
        all_track_ids.extend(track_ids)
        artist_results.append({"name": name, "status": "ok", "tracks": len(track_ids)})
    return all_track_ids, artist_results


@app.route("/api/create-playlist", methods=["POST"])
def create_playlist():
    body = request.get_json()
    artists = body.get("artists", [])
    if not artists:
        return jsonify({"error": "no_artists"}), 400

    try:
        hdrs = spotify_headers()
        all_track_ids, artist_results = _collect_tracks(artists, hdrs)
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
        json={"name": f"Festival Setlist – {today}", "public": False,
              "description": "Created by Festival SetlistFM Creator, an open source project in GitHub: https://github.com/based-on-what/festival-setlistfm"},
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