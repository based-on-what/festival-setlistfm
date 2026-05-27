# Festival Setlist Creator

Build a Spotify playlist from the most recent setlists of your favorite festival artists.

## How It Works

1. Search for artists — the app queries setlist.fm's database with autocomplete.
2. Add up to 20 artists to your Festival Lineup. Drag-and-drop (or tap-to-swap on mobile) to reorder them.
3. Configure playlist options:
   - **Prefer original recording** — when an artist performs a cover, tries to find the original artist's version on Spotify first.
   - **Include taped/backing tracks** — includes songs played from recordings rather than performed live.
   - **Custom playlist name** — defaults to `Festival Setlist – DD/MM/YYYY`.
4. Click **Create Festival Setlist** — the app fetches each artist's most recent setlist from setlist.fm, resolves every song to a Spotify track, and creates a private playlist in your account.
5. A result card appears with a per-artist summary, warnings for missing tracks, and an embedded Spotify player.

**Medley handling:** songs listed as `Song A / Song B` are automatically split and searched individually.

---

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `SPOTIPY_CLIENT_ID` | Yes | Spotify app client ID |
| `SPOTIPY_CLIENT_SECRET` | Yes | Spotify app client secret |
| `SPOTIPY_REFRESH_TOKEN` | Yes | Long-lived Spotify refresh token (see below) |
| `SETLISTFM_API_KEY` | Yes | setlist.fm API key |
| `PORT` | No | Server port (default: `3000`) |

---

## Local Setup

```bash
# 1. Clone / enter the project
cd festival-setlistfm

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create a .env file with your keys
# SPOTIPY_CLIENT_ID=...
# SPOTIPY_CLIENT_SECRET=...
# SPOTIPY_REFRESH_TOKEN=...
# SETLISTFM_API_KEY=...

# 5. Run the app
python app.py
# Open http://localhost:3000
```

---

## Railway Deploy

1. Push this repository to GitHub.
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**.
3. Select the repository.
4. In **Variables**, add the four required env vars from the table above.
5. Railway auto-detects the `Procfile` and deploys (gunicorn, 2 workers, 4 threads).

---

## API Reference

### `GET /api/search-artist?q=<name>`

Returns artists matching the query from setlist.fm.

**Rate limit:** 60 requests/minute.

**Response:**

```json
{
  "artists": [
    {
      "id": "mbid-or-name",
      "mbid": "musicbrainz-id",
      "name": "Artist Name",
      "sortName": "Name, Artist",
      "disambiguation": "band era or type",
      "url": "https://www.setlist.fm/..."
    }
  ]
}
```

### `POST /api/create-playlist`

Fetches setlists, resolves tracks, and creates a Spotify playlist.

**Rate limit:** 5 requests/minute.

**Request body:**

```json
{
  "artists": [{ "id": "...", "mbid": "...", "name": "..." }],
  "prefer_original": true,
  "include_taped": false,
  "playlist_name": "My Festival"
}
```

**Response:**

```json
{
  "playlist_url": "https://open.spotify.com/playlist/...",
  "playlist_id": "...",
  "total_tracks": 150,
  "failed_chunks": 0,
  "artists": [
    { "name": "Artist", "status": "ok", "tracks": 25, "missing": [] }
  ]
}
```

Artist `status` values: `ok`, `no_tracks`, `no_setlist`.

---

## Getting API Keys

### Spotify

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) and log in.
2. Click **Create App**. Fill in name and description.
3. Copy **Client ID** and **Client Secret** — these are `SPOTIPY_CLIENT_ID` and `SPOTIPY_CLIENT_SECRET`.
4. To get the **Refresh Token**, run `tokens.py` (included in this repo) or use a tool like the [Spotify Refresh Token Generator](https://github.com/kylesarre/Spotify-RefreshTokenGenerator). Required scopes: `playlist-modify-private playlist-modify-public`.

### setlist.fm

1. Go to [api.setlist.fm](https://api.setlist.fm) and create a free account.
2. Apply for an API key from your account settings.
3. Copy the key into `SETLISTFM_API_KEY`.

---

## Tech Stack

- **Backend:** Flask 3, Requests, python-dotenv, Flask-Limiter, gunicorn
- **APIs:** Spotify Web API, setlist.fm API v1
- **Frontend:** Vanilla JS, Space Mono font, mobile-drag-drop (CDN)
- **Concurrency:** `ThreadPoolExecutor` (32 workers) for parallel artist/track resolution
- **Caching:** In-memory TTL cache (1 hour) for setlist.fm responses
