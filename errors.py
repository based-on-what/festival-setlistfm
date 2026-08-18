"""Error-code constants shared across backend modules.

The string values are an API contract with the frontend catalog
ERROR_MESSAGES in static/app.js — never change a value without
updating the catalog (tests/test_error_contract.py enforces this).
"""

# setlist.fm
SETLISTFM_NOT_CONFIGURED   = "setlistfm_not_configured"
SETLISTFM_TIMEOUT          = "setlistfm_timeout"
SETLISTFM_CONNECTION_ERROR = "setlistfm_connection_error"
SETLISTFM_API_KEY_INVALID  = "setlistfm_api_key_invalid"
SETLISTFM_RATE_LIMITED     = "setlistfm_rate_limited"
SETLISTFM_QUOTA_EXCEEDED   = "setlistfm_quota_exceeded"  # 403: cupo diario agotado
SETLISTFM_HTTP_PREFIX      = "setlistfm_http_"  # dynamic: setlistfm_http_<status>

# Spotify
SPOTIFY_NOT_CONFIGURED           = "spotify_not_configured"
SPOTIFY_REFRESH_TOKEN_MISSING    = "spotify_refresh_token_missing"
SPOTIFY_REFRESH_TOKEN_INVALID    = "spotify_refresh_token_invalid"
SPOTIFY_CREDENTIALS_INVALID      = "spotify_credentials_invalid"
SPOTIFY_AUTH_TIMEOUT             = "spotify_auth_timeout"
SPOTIFY_AUTH_CONNECTION_ERROR    = "spotify_auth_connection_error"
SPOTIFY_AUTH_HTTP_PREFIX         = "spotify_auth_http_"  # dynamic: spotify_auth_http_<status>
SPOTIFY_TOKEN_EXPIRED            = "spotify_token_expired"
SPOTIFY_NETWORK_ERROR            = "spotify_network_error"
SPOTIFY_COULD_NOT_GET_USER       = "spotify_could_not_get_user"
SPOTIFY_PLAYLIST_CREATION_FAILED = "spotify_playlist_creation_failed"

# Request validation / results
NO_ARTISTS       = "no_artists"
TOO_MANY_ARTISTS = "too_many_artists"
NO_TRACKS_FOUND  = "no_tracks_found"
JOB_NOT_FOUND    = "job_not_found"

# Every static code the frontend catalog must know about (prefixes are
# matched by the frontend's _http_NNN regex and excluded here).
FRONTEND_CATALOG_CODES = [
    SETLISTFM_NOT_CONFIGURED,
    SETLISTFM_TIMEOUT,
    SETLISTFM_CONNECTION_ERROR,
    SETLISTFM_API_KEY_INVALID,
    SETLISTFM_RATE_LIMITED,
    SETLISTFM_QUOTA_EXCEEDED,
    SPOTIFY_NOT_CONFIGURED,
    SPOTIFY_REFRESH_TOKEN_MISSING,
    SPOTIFY_REFRESH_TOKEN_INVALID,
    SPOTIFY_CREDENTIALS_INVALID,
    SPOTIFY_AUTH_TIMEOUT,
    SPOTIFY_AUTH_CONNECTION_ERROR,
    SPOTIFY_TOKEN_EXPIRED,
    SPOTIFY_NETWORK_ERROR,
    SPOTIFY_COULD_NOT_GET_USER,
    SPOTIFY_PLAYLIST_CREATION_FAILED,
    NO_ARTISTS,
    TOO_MANY_ARTISTS,
    NO_TRACKS_FOUND,
    JOB_NOT_FOUND,
]
