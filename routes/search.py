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
            return jsonify({"artists": [], "has_more": False})

        try:
            page = max(1, min(int(request.args.get("p", "1")), 10))
        except ValueError:
            page = 1

        artists, err, has_more = setlistfm.search_artists(q, page)

        if err == errors.SETLISTFM_NOT_CONFIGURED:
            return jsonify({"error": err}), 503
        if err in (errors.SETLISTFM_RATE_LIMITED, errors.SETLISTFM_QUOTA_EXCEEDED):
            return jsonify({"error": err}), 429
        if err:
            status = 504 if "timeout" in err else 502
            return jsonify({"error": err}), status

        return jsonify({"artists": artists, "has_more": has_more})

    return bp
