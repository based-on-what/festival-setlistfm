import logging
import os
from concurrent.futures import ThreadPoolExecutor

import requests
from dotenv import load_dotenv
from flask import Flask, render_template
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


def create_app(config: Config = None) -> Flask:
    config   = config or Config.from_env()
    executor = ThreadPoolExecutor(max_workers=config.thread_pool_workers)

    spotify   = SpotifyClient(config, requests.Session(), requests.Session())
    setlistfm = SetlistFMClient(config, requests.Session(), TTLCache(ttl=config.setlist_cache_ttl))
    resolver  = TrackResolver(spotify, executor)
    builder   = PlaylistBuilder(setlistfm, resolver, spotify, executor)

    app = Flask(__name__)
    limiter = Limiter(get_remote_address, app=app, default_limits=["200/minute"])

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return resp

    @app.route("/", methods=["GET"])
    def index():
        return render_template("index.html")

    app.register_blueprint(create_search_blueprint(setlistfm, limiter))
    app.register_blueprint(create_playlist_blueprint(config, builder, limiter))

    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    create_app().run(host="0.0.0.0", port=port, debug=False)
