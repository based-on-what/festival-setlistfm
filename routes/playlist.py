import logging
from datetime import date

import requests
from flask import Blueprint, request, jsonify

from config import Config
from services.playlist_builder import PlaylistBuilder

log = logging.getLogger(__name__)


def create_playlist_blueprint(config: Config, builder: PlaylistBuilder, limiter) -> Blueprint:
    bp = Blueprint("playlist", __name__)

    @bp.route("/api/create-playlist", methods=["POST"])
    @limiter.limit("5/minute")
    def create_playlist():
        body    = request.get_json(silent=True) or {}
        artists = body.get("artists", [])

        if not artists:
            return jsonify({"error": "no_artists"}), 400
        if len(artists) > config.max_artists:
            return jsonify({"error": "too_many_artists"}), 400

        artists = [a for a in artists if isinstance(a, dict) and a.get("name", "").strip()]
        if not artists:
            return jsonify({"error": "no_artists"}), 400

        prefer_original = bool(body.get("prefer_original", True))
        include_taped   = bool(body.get("include_taped", False))
        today           = date.today().strftime("%d/%m/%Y")
        playlist_name   = body.get("playlist_name", "").strip() or f"Festival Setlist – {today}"

        try:
            result = builder.build(artists, prefer_original, include_taped, playlist_name)
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 503
        except requests.RequestException as e:
            log.error("spotify network error: %s", e)
            return jsonify({"error": "spotify_network_error"}), 503

        if "error" in result:
            return jsonify(result), 400

        return jsonify(result)

    return bp
