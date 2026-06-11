from flask import Blueprint, request, jsonify

import errors
from infrastructure.setlistfm_client import SetlistFMClient


def create_search_blueprint(setlistfm: SetlistFMClient, limiter) -> Blueprint:
    bp = Blueprint("search", __name__)

    @bp.route("/api/search-artist")
    @limiter.limit("60/minute")
    def search_artist():
        q = request.args.get("q", "").strip()
        if not q:
            return jsonify({"artists": []})

        artists, err = setlistfm.search_artists(q)

        if err == errors.SETLISTFM_NOT_CONFIGURED:
            return jsonify({"error": err}), 503
        if err == errors.SETLISTFM_RATE_LIMITED:
            return jsonify({"error": err}), 429
        if err:
            status = 504 if "timeout" in err else 502
            return jsonify({"error": err}), status

        return jsonify({"artists": artists})

    return bp
