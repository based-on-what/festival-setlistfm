# Festival Setlist Creator

Build a Spotify playlist from the most recent setlists of your favorite festival artists.

## How It Works

1. Search for artists and add them to your list.
2. Click **Create Festival Setlist** — the app fetches each artist's most recent setlist from setlist.fm, matches the songs on Spotify, and creates a private playlist in your account.

---

## Environment Variables

| Variable | Description |
| --- | --- |
| `SPOTIFY_CLIENT_ID` | Your Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | Your Spotify app client secret |
| `SPOTIFY_REDIRECT_URI` | OAuth callback URL used during one-time setup (e.g. `http://localhost:3000/callback`) |
| `SPOTIFY_REFRESH_TOKEN` | Long-lived token obtained via `/setup` — allows the app to operate without user login |
| `SETLISTFM_API_KEY` | Your setlist.fm API key |

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
4. In **Variables**, add the env vars from the table above (except `SPOTIFY_REFRESH_TOKEN` — you'll get it next).
   - Set `SPOTIFY_REDIRECT_URI` to `https://<your-railway-domain>/callback`
5. Update your Spotify app's **Redirect URIs** to include that Railway URL.
6. Railway auto-detects the `Procfile` and deploys.
7. Visit `https://<your-railway-domain>/setup` once to authorize the app with Spotify. Copy the `SPOTIFY_REFRESH_TOKEN` shown on screen and add it to your Railway variables.
8. Redeploy (or restart the service) — the app is now fully operational with no login required.

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
