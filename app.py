import os
import time
import requests
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

SPOTIPY_CLIENT_ID     = os.environ.get("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.environ.get("SPOTIPY_CLIENT_SECRET")
SETLISTFM_API_KEY     = os.environ.get("SETLISTFM_API_KEY")

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE  = "https://api.spotify.com/v1"
SETLISTFM_API_BASE = "https://api.setlist.fm/rest/1.0"

_access_token  = None
_token_expiry  = 0
_token_lock    = __import__("threading").Lock()   # FIX: protege acceso concurrente al token


# ── Token management ───────────────────────────────────────────────────────────

def get_access_token():
    """
    Obtiene (o renueva) el access token de Spotify.
    Lanza RuntimeError con mensajes claros si algo falla.
    """
    global _access_token, _token_expiry
    with _token_lock:
        if _access_token and time.time() < _token_expiry - 60:
            return _access_token

        # Validar configuración antes de hacer la petición
        if not SPOTIPY_CLIENT_ID or not SPOTIPY_CLIENT_SECRET:
            raise RuntimeError("spotify_not_configured")

        refresh_token = os.environ.get("SPOTIPY_REFRESH_TOKEN")
        if not refresh_token:
            raise RuntimeError("spotify_refresh_token_missing")

        try:
            resp = requests.post(
                SPOTIFY_TOKEN_URL,
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
                auth=(SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET),
                timeout=10,  # FIX: timeout que antes no existía
            )
        except requests.Timeout:
            raise RuntimeError("spotify_auth_timeout")
        except requests.ConnectionError:
            raise RuntimeError("spotify_auth_connection_error")

        # FIX: error más descriptivo según el status code
        if resp.status_code == 400:
            raise RuntimeError("spotify_refresh_token_invalid")
        if resp.status_code == 401:
            raise RuntimeError("spotify_credentials_invalid")
        if not resp.ok:
            raise RuntimeError(f"spotify_auth_http_{resp.status_code}")

        data = resp.json()
        _access_token = data["access_token"]
        _token_expiry = time.time() + data.get("expires_in", 3600)
        return _access_token


def spotify_headers():
    return {"Authorization": f"Bearer {get_access_token()}"}


# ── Index ──────────────────────────────────────────────────────────────────────

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
        return jsonify({"error": "setlistfm_not_configured"}), 503

    try:
        resp = requests.get(
            f"{SETLISTFM_API_BASE}/search/artists",
            headers={"x-api-key": SETLISTFM_API_KEY, "Accept": "application/json"},
            params={"artistName": q, "sort": "relevance", "p": 1},
            timeout=6,  # FIX: timeout que antes era 5s pero no en todos los endpoints
        )
    except requests.Timeout:
        return jsonify({"error": "setlistfm_timeout"}), 504
    except requests.ConnectionError:
        return jsonify({"error": "setlistfm_connection_error"}), 503

    # FIX: distinción de errores según status code
    if resp.status_code == 401:
        return jsonify({"error": "setlistfm_api_key_invalid"}), 502
    if resp.status_code == 404:
        return jsonify({"artists": []})
    if resp.status_code == 429:
        return jsonify({"error": "setlistfm_rate_limited"}), 429
    if not resp.ok:
        return jsonify({"error": f"setlistfm_http_{resp.status_code}"}), 502

    items = resp.json().get("artist", [])
    artists = []
    for a in items[:8]:
        artists.append({
            "id":             a.get("mbid", a.get("name")),
            "mbid":           a.get("mbid"),
            "name":           a.get("name", ""),
            "sortName":       a.get("sortName", ""),
            "disambiguation": a.get("disambiguation", ""),
            "url":            a.get("url", ""),
            "image":          None,
        })
    return jsonify({"artists": artists})


# ── Setlist helpers ────────────────────────────────────────────────────────────

def _extract_songs(setlist, include_taped):
    songs = []
    for sset in setlist.get("sets", {}).get("set", []):
        for song in sset.get("song", []):
            name = song.get("name", "").strip()
            if not name:
                continue
            is_tape = bool(song.get("tape", False))
            if is_tape and not include_taped:
                continue
            cover_info   = song.get("cover")
            cover_artist = cover_info.get("name") if cover_info else None
            songs.append({
                "name":               name,
                "cover_artist":       cover_artist,
                "is_medley_candidate": " / " in name,
                "is_tape":            is_tape,
            })
    return songs


def _get_recent_setlist(mbid, artist_name, include_taped):
    """
    FIX: ahora propaga errores de autenticación en lugar de silenciarlos,
    e incluye timeout en cada petición.
    Retorna (songs | None, error_code | None).
    """
    if not SETLISTFM_API_KEY:
        return None, "setlistfm_not_configured"

    headers = {"x-api-key": SETLISTFM_API_KEY, "Accept": "application/json"}

    if mbid:
        url         = f"{SETLISTFM_API_BASE}/artist/{mbid}/setlists"
        base_params = {}
    else:
        url         = f"{SETLISTFM_API_BASE}/search/setlists"
        base_params = {"artistName": artist_name}

    for page in range(1, 6):
        params = {**base_params, "p": page}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=8)
        except requests.Timeout:
            return None, "setlistfm_timeout"
        except requests.ConnectionError:
            return None, "setlistfm_connection_error"

        if resp.status_code in (401, 403):
            return None, "setlistfm_api_key_invalid"
        if resp.status_code == 429:
            return None, "setlistfm_rate_limited"
        if resp.status_code == 404:
            return None, None   # artista sin setlists
        if not resp.ok:
            return None, None   # cualquier otro error HTTP → sin setlist

        setlists = resp.json().get("setlist", [])
        if not setlists:
            return None, None   # sin más páginas

        for setlist in setlists:
            songs = _extract_songs(setlist, include_taped)
            if len(songs) >= 3:
                return songs, None

    return None, None


# ── Spotify track resolution ───────────────────────────────────────────────────

def _search_spotify_track(hdrs, artist_name, track_name):
    """FIX: timeout en todas las llamadas a Spotify."""
    try:
        r = requests.get(
            f"{SPOTIFY_API_BASE}/search",
            headers=hdrs,
            params={
                "q":     f'artist:"{artist_name}" track:"{track_name}"',
                "type":  "track",
                "limit": 1,
            },
            timeout=6,
        )
    except (requests.Timeout, requests.ConnectionError):
        return None
    if r.ok:
        items = r.json().get("tracks", {}).get("items", [])
        if items:
            return items[0]["id"]
    return None


def _search_spotify_track_any_artist(hdrs, track_name):
    try:
        r = requests.get(
            f"{SPOTIFY_API_BASE}/search",
            headers=hdrs,
            params={"q": f'track:"{track_name}"', "type": "track", "limit": 1},
            timeout=6,
        )
    except (requests.Timeout, requests.ConnectionError):
        return None
    if r.ok:
        items = r.json().get("tracks", {}).get("items", [])
        if items:
            return items[0]["id"]
    return None


def _resolve_track(hdrs, performing_artist, song, prefer_original):
    name                 = song["name"]
    cover_artist         = song["cover_artist"]
    is_medley_candidate  = song["is_medley_candidate"]

    if prefer_original and cover_artist:
        tid = _search_spotify_track(hdrs, cover_artist, name)
        if not tid:
            tid = _search_spotify_track(hdrs, performing_artist, name)
    else:
        tid = _search_spotify_track(hdrs, performing_artist, name)
        if not tid and cover_artist:
            tid = _search_spotify_track(hdrs, cover_artist, name)

    if tid:
        return [tid]

    if is_medley_candidate:
        parts   = [p.strip() for p in name.split(" / ") if p.strip()]
        results = []
        for part in parts:
            if prefer_original and cover_artist:
                t = _search_spotify_track(hdrs, cover_artist, part)
                if not t:
                    t = _search_spotify_track(hdrs, performing_artist, part)
            else:
                t = _search_spotify_track(hdrs, performing_artist, part)
                if not t and cover_artist:
                    t = _search_spotify_track(hdrs, cover_artist, part)
            if not t:
                t = _search_spotify_track_any_artist(hdrs, part)
            if t:
                results.append(t)
        return results

    return []


def _find_tracks_parallel(hdrs, performing_artist, songs, prefer_original):
    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(_resolve_track, hdrs, performing_artist, song, prefer_original): song
            for song in songs
        }
        for future in as_completed(futures):
            song = futures[future]
            try:
                # FIX: antes future.result() podía lanzar y crashear todo el endpoint
                track_ids = future.result()
            except Exception:
                track_ids = []
            results.append((song["name"], track_ids))

    all_ids = []
    missing = []
    for song_name, track_ids in results:
        if track_ids:
            all_ids.extend(track_ids)
        else:
            missing.append(song_name)

    return all_ids, missing


def _collect_tracks(artists, hdrs, prefer_original, include_taped):
    all_track_ids  = []
    artist_results = []

    for artist in artists:
        name  = artist.get("name", "")
        mbid  = artist.get("mbid")
        songs, err = _get_recent_setlist(mbid, name, include_taped)

        if err in ("setlistfm_api_key_invalid", "setlistfm_rate_limited"):
            # FIX: errores fatales de autenticación/rate-limit → propagar arriba
            raise RuntimeError(err)

        if not songs:
            artist_results.append({
                "name":    name,
                "status":  "no_setlist",
                "tracks":  0,
                "missing": [],
            })
            continue

        track_ids, missing = _find_tracks_parallel(hdrs, name, songs, prefer_original)
        all_track_ids.extend(track_ids)
        artist_results.append({
            "name":    name,
            "status":  "ok" if track_ids else "no_tracks",
            "tracks":  len(track_ids),
            "missing": missing,
        })

    return all_track_ids, artist_results


# ── Create playlist endpoint ───────────────────────────────────────────────────

@app.route("/api/create-playlist", methods=["POST"])
def create_playlist():
    body    = request.get_json(silent=True) or {}
    artists = body.get("artists", [])

    if not artists:
        return jsonify({"error": "no_artists"}), 400

    prefer_original = bool(body.get("prefer_original", True))
    include_taped   = bool(body.get("include_taped", False))
    today           = date.today().strftime("%d/%m/%Y")
    playlist_name   = body.get("playlist_name", "").strip() or f"Festival Setlist – {today}"

    # FIX: captura RuntimeError Y requests.RequestException (HTTPError, Timeout, etc.)
    try:
        hdrs = spotify_headers()
        all_track_ids, artist_results = _collect_tracks(
            artists, hdrs, prefer_original, include_taped
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except requests.RequestException as e:
        return jsonify({"error": "spotify_network_error", "detail": str(e)}), 503

    if not all_track_ids:
        return jsonify({"error": "no_tracks_found", "details": artist_results}), 400

    # ── Obtener usuario ────────────────────────────────────────────────────────
    try:
        me = requests.get(f"{SPOTIFY_API_BASE}/me", headers=hdrs, timeout=8)
    except requests.RequestException:
        return jsonify({"error": "spotify_network_error"}), 503

    if me.status_code == 401:
        return jsonify({"error": "spotify_token_expired"}), 401
    if not me.ok:
        return jsonify({"error": "spotify_could_not_get_user"}), 502

    user_id = me.json()["id"]

    # ── Crear playlist ─────────────────────────────────────────────────────────
    try:
        pl = requests.post(
            f"{SPOTIFY_API_BASE}/users/{user_id}/playlists",
            headers={**hdrs, "Content-Type": "application/json"},
            json={
                "name":        playlist_name,
                "public":      False,
                "description": "Created by Festival SetlistFM Creator – https://github.com/based-on-what/festival-setlistfm",
            },
            timeout=10,
        )
    except requests.RequestException:
        return jsonify({"error": "spotify_network_error"}), 503

    if not pl.ok:
        return jsonify({"error": "spotify_playlist_creation_failed"}), 502

    playlist_id  = pl.json()["id"]
    playlist_url = pl.json()["external_urls"]["spotify"]

    # ── Añadir tracks en chunks ────────────────────────────────────────────────
    failed_chunks = 0
    for i in range(0, len(all_track_ids), 100):
        chunk = all_track_ids[i: i + 100]
        try:
            # FIX: antes no se verificaba si la inserción de tracks fallaba
            r = requests.post(
                f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks",
                headers={**hdrs, "Content-Type": "application/json"},
                json={"uris": [f"spotify:track:{tid}" for tid in chunk]},
                timeout=10,
            )
            if not r.ok:
                failed_chunks += 1
        except requests.RequestException:
            failed_chunks += 1

    return jsonify({
        "playlist_url":   playlist_url,
        "playlist_id":    playlist_id,
        "total_tracks":   len(all_track_ids),
        "failed_chunks":  failed_chunks,        # FIX: informa al frontend si algunos chunks fallaron
        "artists":        artist_results,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=False)