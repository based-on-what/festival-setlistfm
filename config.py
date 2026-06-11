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
    setlistfm_rate_per_sec: float = 2.0
    build_deadline_seconds: float = 90.0

    def validate(self) -> list[str]:
        """Names of required env vars that are missing/empty."""
        required = {
            "SPOTIPY_CLIENT_ID":     self.spotify_client_id,
            "SPOTIPY_CLIENT_SECRET": self.spotify_client_secret,
            "SPOTIPY_REFRESH_TOKEN": self.spotify_refresh_token,
            "SETLISTFM_API_KEY":     self.setlistfm_api_key,
        }
        return [name for name, value in required.items() if not value]

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            spotify_client_id=os.environ.get("SPOTIPY_CLIENT_ID", ""),
            spotify_client_secret=os.environ.get("SPOTIPY_CLIENT_SECRET", ""),
            spotify_refresh_token=os.environ.get("SPOTIPY_REFRESH_TOKEN", ""),
            setlistfm_api_key=os.environ.get("SETLISTFM_API_KEY", ""),
        )
