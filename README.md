# Festival Setlist Creator

Build a Spotify playlist from the most recent setlists of your favorite festival artists.

## How It Works

1. Authenticate with Spotify.
2. Search for artists and add them to your list.
3. Click **Create Festival Setlist** — the app fetches each artist's most recent setlist from setlist.fm, matches the songs on Spotify, and creates a private playlist in your account.

---

## Environment Variables

| Variable | Description |
|---|---|
| `SPOTIFY_CLIENT_ID` | Your Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | Your Spotify app client secret |
| `SPOTIFY_REDIRECT_URI` | OAuth callback URL (e.g. `http://localhost:3000/callback`) |
| `SETLISTFM_API_KEY` | Your setlist.fm API key |
| `SECRET_KEY` | Random string used for Flask session signing |

---

## Local Setup

```bash
# 1. Clone / enter the project
cd festivalSetlistFm

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and fill in environment variables
cp .env.example .env
# Edit .env with your actual keys

# 5. Run the app
python app.py
# Open http://localhost:3000
```

---

## Railway Deploy

1. Push this repository to GitHub.
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**.
3. Select the repository.
4. In **Variables**, add all five env vars from the table above.
   - Set `SPOTIFY_REDIRECT_URI` to `https://<your-railway-domain>/callback`
5. Railway auto-detects the `Procfile` and deploys.
6. Once live, update your Spotify app's **Redirect URI** to match the Railway URL.

---

## Getting API Keys

### Spotify

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) and log in.
2. Click **Create App**.
3. Fill in name + description. Under **Redirect URIs** add `http://localhost:3000/callback` (and your Railway URL when deploying).
4. Copy **Client ID** and **Client Secret** into your `.env`.

### setlist.fm

1. Go to [api.setlist.fm](https://api.setlist.fm) and create a free account.
2. Apply for an API key from your account settings.
3. Copy the key into `SETLISTFM_API_KEY` in your `.env`.
