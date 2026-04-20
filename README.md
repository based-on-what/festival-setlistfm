# Festival Setlist Creator

Build a Spotify playlist from the most recent setlists of your favorite festival artists.

## How It Works

1. Search for artists and add them to your list.
2. Click **Create Festival Setlist** — the app fetches each artist's most recent setlist from setlist.fm, matches the songs on Spotify, and creates a private playlist in your account.

---

## Environment Variables

| Variable | Description |
| --- | --- |
| `SPOTIPY_CLIENT_ID` | Your Spotify app client ID |
| `SPOTIPY_CLIENT_SECRET` | Your Spotify app client secret |
| `SPOTIPY_REFRESH_TOKEN` | Long-lived Spotify refresh token (see below to obtain it) |
| `SETLISTFM_API_KEY` | Your setlist.fm API key |

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
4. In **Variables**, add the four env vars from the table above.
5. Railway auto-detects the `Procfile` and deploys.

---

## Getting API Keys

### Spotify

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) and log in.
2. Click **Create App**. Fill in name + description.
3. Copy **Client ID** and **Client Secret** — these are `SPOTIPY_CLIENT_ID` and `SPOTIPY_CLIENT_SECRET`.
4. To get the **Refresh Token**, use a tool like [Spotify Refresh Token Generator](https://github.com/kylesarre/Spotify-RefreshTokenGenerator) or the Spotipy CLI (`spotipy-oauth2`) with scopes `playlist-modify-private playlist-modify-public`.

### setlist.fm

1. Go to [api.setlist.fm](https://api.setlist.fm) and create a free account.
2. Apply for an API key from your account settings.
3. Copy the key into `SETLISTFM_API_KEY`.
