import os
import time
import requests
from datetime import date
from flask import Flask, request, jsonify, render_template, redirect
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

_access_token = None
_token_expiry = 0


def get_access_token():
    global _access_token, _token_expiry
    if _access_token and time.time() < _token_expiry - 60:
        return _access_token
    refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN")
    if not refresh_token:
        raise RuntimeError("SPOTIFY_REFRESH_TOKEN not configured. Visit /setup first.")
    resp = requests.post(
        SPOTIFY_TOKEN_URL,
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET),
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


# ── One-time setup routes (get the refresh token once, then store in .env) ──

@app.route("/setup")
def setup():
    scope = "playlist-modify-private playlist-modify-public"
    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": scope,
        "show_dialog": "true",
    }
    return redirect(f"{SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(params)}")


@app.route("/callback")
def callback():
    code = request.args.get("code")
    error = request.args.get("error")
    if error or not code:
        return "<h3>Auth error — try /setup again.</h3>", 400
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
        return "<h3>Token exchange failed — check your credentials.</h3>", 400
    data = resp.json()
    rt = data.get("refresh_token", "")
    return f"""<!DOCTYPE html>
<html><head><title>Setup</title>
<style>
  body{{background:#0d0d0d;color:#f0f0f0;font-family:monospace;padding:48px;max-width:600px;margin:auto}}
  pre{{background:#1a1a1a;border:1px solid #2e2e2e;padding:20px;border-radius:8px;word-break:break-all;white-space:pre-wrap}}
  h2{{color:#1db954;margin-bottom:16px}}
  p{{color:#888;margin-bottom:12px;line-height:1.5}}
</style>
</head><body>
<h2>Setup complete ✓</h2>
<p>Copy the line below into your <code>.env</code> file (or Railway environment variables), then restart the app.</p>
<pre>SPOTIFY_REFRESH_TOKEN={rt}</pre>
<p>After restarting, visit <a href="/" style="color:#1db954">the app</a>.</p>
</body></html>"""


# ── API routes ──

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
