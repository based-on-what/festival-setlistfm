import os
import time
import requests
from datetime import date
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
    artists = [
        {
            "id": a["id"],
            "name": a["name"],
            "image": a["images"][-1]["url"] if a.get("images") else None,
        }
        for a in items
    ]
    return jsonify({"artists": artists})


def _get_recent_setlist(artist_name):
    headers = {"x-api-key": SETLISTFM_API_KEY, "Accept": "application/json"}
    for page in range(1, 6):
        resp = requests.get(
            f"{SETLISTFM_API_BASE}/search/setlists",
            headers=headers,
            params={"artistName": artist_name, "p": page},
        )
        if not resp.ok:
            return None
        setlists = resp.json().get("setlist", [])
        if not setlists:
            return None
        for setlist in setlists:
            songs = [
                song.get("name", "").strip()
                for sset in setlist.get("sets", {}).get("set", [])
                for song in sset.get("song", [])
                if song.get("name", "").strip()
            ]
            if len(songs) >= 3:
                return songs
    return None


@app.route("/api/create-playlist", methods=["POST"])
def create_playlist():
    body = request.get_json()
    artists = body.get("artists", [])
    if not artists:
        return jsonify({"error": "no_artists"}), 400

    try:
        hdrs = spotify_headers()
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    all_track_ids = []
    artist_results = []

    for artist in artists:
        name = artist.get("name", "")
        songs = _get_recent_setlist(name)
        if not songs:
            artist_results.append({"name": name, "status": "no_setlist", "tracks": 0})
            continue

        track_ids = []
        for song in songs:
            r = requests.get(
                f"{SPOTIFY_API_BASE}/search",
                headers=hdrs,
                params={"q": f"artist:{name} track:{song}", "type": "track", "limit": 1},
            )
            if r.ok:
                items = r.json().get("tracks", {}).get("items", [])
                if items:
                    track_ids.append(items[0]["id"])

        all_track_ids.extend(track_ids)
        artist_results.append({"name": name, "status": "ok", "tracks": len(track_ids)})

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
              "description": "Created by Festival Setlist Creator"},
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
