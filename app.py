import os
import requests
from datetime import date
from flask import Flask, request, jsonify, render_template, redirect, session, url_for
from dotenv import load_dotenv
import urllib.parse
import secrets

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI")
SETLISTFM_API_KEY = os.environ.get("SETLISTFM_API_KEY")

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SETLISTFM_API_BASE = "https://api.setlist.fm/rest/1.0"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login")
def login():
    scope = "playlist-modify-private playlist-modify-public"
    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": scope,
        "state": secrets.token_hex(8),
    }
    return redirect(f"{SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(params)}")


@app.route("/callback")
def callback():
    code = request.args.get("code")
    error = request.args.get("error")
    if error or not code:
        return redirect("/?error=auth_failed")
    resp = requests.post(
        SPOTIFY_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": SPOTIFY_REDIRECT_URI,
        },
        auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET),
    )
    if not resp.ok:
        return redirect("/?error=token_failed")
    data = resp.json()
    session["access_token"] = data["access_token"]
    session["refresh_token"] = data.get("refresh_token")
    return redirect("/")


@app.route("/api/auth-status")
def auth_status():
    return jsonify({"authenticated": "access_token" in session})


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


def _refresh_token():
    refresh_token = session.get("refresh_token")
    if not refresh_token:
        return False
    resp = requests.post(
        SPOTIFY_TOKEN_URL,
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET),
    )
    if not resp.ok:
        return False
    session["access_token"] = resp.json()["access_token"]
    return True


def _spotify_headers():
    return {"Authorization": f"Bearer {session['access_token']}"}


@app.route("/api/search-artist")
def search_artist():
    if "access_token" not in session:
        return jsonify({"error": "not_authenticated"}), 401
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"artists": []})
    resp = requests.get(
        f"{SPOTIFY_API_BASE}/search",
        headers=_spotify_headers(),
        params={"q": q, "type": "artist", "limit": 8},
    )
    if resp.status_code == 401:
        if _refresh_token():
            resp = requests.get(
                f"{SPOTIFY_API_BASE}/search",
                headers=_spotify_headers(),
                params={"q": q, "type": "artist", "limit": 8},
            )
        else:
            return jsonify({"error": "auth_expired"}), 401
    if not resp.ok:
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
    headers = {
        "x-api-key": SETLISTFM_API_KEY,
        "Accept": "application/json",
    }
    page = 1
    while page <= 5:
        resp = requests.get(
            f"{SETLISTFM_API_BASE}/search/setlists",
            headers=headers,
            params={"artistName": artist_name, "p": page},
        )
        if not resp.ok:
            return None
        data = resp.json()
        setlists = data.get("setlist", [])
        if not setlists:
            return None
        for setlist in setlists:
            songs = []
            for sset in setlist.get("sets", {}).get("set", []):
                for song in sset.get("song", []):
                    name = song.get("name", "").strip()
                    if name:
                        songs.append(name)
            if len(songs) >= 3:
                return songs
        page += 1
    return None


@app.route("/api/create-playlist", methods=["POST"])
def create_playlist():
    if "access_token" not in session:
        return jsonify({"error": "not_authenticated"}), 401

    body = request.get_json()
    artists = body.get("artists", [])
    if not artists:
        return jsonify({"error": "no_artists"}), 400

    all_track_ids = []
    artist_results = []

    for artist in artists:
        artist_name = artist.get("name", "")
        songs = _get_recent_setlist(artist_name)
        if not songs:
            artist_results.append({"name": artist_name, "status": "no_setlist", "tracks": 0})
            continue

        track_ids = []
        for song in songs:
            search_resp = requests.get(
                f"{SPOTIFY_API_BASE}/search",
                headers=_spotify_headers(),
                params={"q": f"artist:{artist_name} track:{song}", "type": "track", "limit": 1},
            )
            if search_resp.status_code == 401:
                if _refresh_token():
                    search_resp = requests.get(
                        f"{SPOTIFY_API_BASE}/search",
                        headers=_spotify_headers(),
                        params={"q": f"artist:{artist_name} track:{song}", "type": "track", "limit": 1},
                    )
                else:
                    return jsonify({"error": "auth_expired"}), 401
            if search_resp.ok:
                tracks = search_resp.json().get("tracks", {}).get("items", [])
                if tracks:
                    track_ids.append(tracks[0]["id"])

        all_track_ids.extend(track_ids)
        artist_results.append({"name": artist_name, "status": "ok", "tracks": len(track_ids)})

    if not all_track_ids:
        return jsonify({"error": "no_tracks_found", "details": artist_results}), 400

    me_resp = requests.get(f"{SPOTIFY_API_BASE}/me", headers=_spotify_headers())
    if not me_resp.ok:
        return jsonify({"error": "could_not_get_user"}), 502
    user_id = me_resp.json()["id"]

    today = date.today().strftime("%Y-%m-%d")
    playlist_resp = requests.post(
        f"{SPOTIFY_API_BASE}/users/{user_id}/playlists",
        headers={**_spotify_headers(), "Content-Type": "application/json"},
        json={"name": f"Festival Setlist – {today}", "public": False, "description": "Created by Festival Setlist Creator"},
    )
    if not playlist_resp.ok:
        return jsonify({"error": "playlist_creation_failed"}), 502
    playlist = playlist_resp.json()
    playlist_id = playlist["id"]
    playlist_url = playlist["external_urls"]["spotify"]

    for i in range(0, len(all_track_ids), 100):
        chunk = all_track_ids[i : i + 100]
        requests.post(
            f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks",
            headers={**_spotify_headers(), "Content-Type": "application/json"},
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
