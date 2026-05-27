from dataclasses import dataclass
import os

SPOTIFY_TOKEN_URL  = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE   = "https://api.spotify.com/v1"
SETLISTFM_API_BASE = "https://api.setlist.fm/rest/1.0"


@dataclass(frozen=True)
class Config:
    spotify_client_id: str
    spotify_client_secret: str
    spotify_refresh_token: str
    setlistfm_api_key: str
    max_artists: int = 20
    setlist_cache_ttl: int = 3600
    thread_pool_workers: int = 32

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            spotify_client_id=os.environ.get("SPOTIPY_CLIENT_ID", ""),
            spotify_client_secret=os.environ.get("SPOTIPY_CLIENT_SECRET", ""),
            spotify_refresh_token=os.environ.get("SPOTIPY_REFRESH_TOKEN", ""),
            setlistfm_api_key=os.environ.get("SETLISTFM_API_KEY", ""),
        )
