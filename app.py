import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import requests
from requests.adapters import HTTPAdapter
from dotenv import load_dotenv
from flask import Flask, g, jsonify, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config
from infrastructure.cache import TTLCache
from infrastructure.setlistfm_client import SetlistFMClient
from infrastructure.spotify_client import SpotifyClient
from services.track_resolver import TrackResolver
from services.playlist_builder import PlaylistBuilder
from routes.search import create_search_blueprint
from routes.playlist import create_playlist_blueprint

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

log = logging.getLogger(__name__)

# Cache-busting version for /static assets; bump when JS/CSS change.
ASSET_VERSION = "2"


def create_app(
    config: Config = None,
    *,
    spotify: SpotifyClient = None,
    setlistfm: SetlistFMClient = None,
    resolver: TrackResolver = None,
    builder: PlaylistBuilder = None,
    artist_executor: ThreadPoolExecutor = None,
    track_executor: ThreadPoolExecutor = None,
) -> Flask:
    config = config or Config.from_env()

    missing = config.validate()
    if missing:
        # Warn, don't crash: local dev without keys should still serve the UI.
        log.warning(
            "missing configuration: %s — API calls will fail until set",
            ", ".join(missing),
        )

    # INVARIANT: PlaylistBuilder blocks on TrackResolver futures, so they must
    # never share an executor — nested submission deadlocks once artist-level
    # tasks occupy every worker.
    artist_executor = artist_executor or ThreadPoolExecutor(max_workers=config.max_artists)
    track_executor  = track_executor or ThreadPoolExecutor(max_workers=config.thread_pool_workers)
    # Playlist jobs run here (each blocks on artist_executor futures), so this
    # pool must also stay separate from the two above.
    job_executor = ThreadPoolExecutor(max_workers=4)

    def make_session() -> requests.Session:
        # Pool sized to the track executor: with the default 10-connection pool,
        # the other 22 of 32 worker threads would block waiting for a connection.
        session = requests.Session()
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=config.thread_pool_workers)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    # 24h search cache: (artist, track) pairs recur across requests; misses are
    # cached too so absent tracks don't re-query.
    spotify   = spotify or SpotifyClient(config, make_session(), make_session(), TTLCache(ttl=86400))
    setlistfm = setlistfm or SetlistFMClient(config, make_session(), TTLCache(ttl=config.setlist_cache_ttl))
    resolver  = resolver or TrackResolver(spotify, track_executor)
    builder   = builder or PlaylistBuilder(
        setlistfm, resolver, spotify, artist_executor,
        build_deadline_seconds=config.build_deadline_seconds,
    )

    app = Flask(__name__)
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 3600  # static assets, paired with ?v= busting
    # In-memory storage is per gunicorn worker (limits multiply by worker count
    # and reset on deploy); set RATELIMIT_STORAGE_URI (e.g. Redis) in production.
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["200/minute"],
        storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
    )

    @app.before_request
    def assign_request_id():
        g.request_id = uuid.uuid4().hex[:8]

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return resp

    @app.route("/", methods=["GET"])
    def index():
        return render_template(
            "index.html",
            max_artists=config.max_artists,
            asset_version=ASSET_VERSION,
        )

    @app.route("/healthz", methods=["GET"])
    @limiter.exempt
    def healthz():
        return jsonify({"status": "ok"})

    app.register_blueprint(create_search_blueprint(setlistfm, limiter))
    app.register_blueprint(create_playlist_blueprint(config, builder, limiter, job_executor))

    return app


# Module-level app for gunicorn (Procfile: `gunicorn app:app`).
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=False)
