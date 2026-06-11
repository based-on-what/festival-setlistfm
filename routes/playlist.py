import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import requests
from flask import Blueprint, g, jsonify, request

import errors
from config import Config
from services.playlist_builder import PlaylistBuilder

log = logging.getLogger(__name__)

# Finished jobs are kept this long for late polls, then pruned.
_JOB_TTL_SECONDS = 600


def create_playlist_blueprint(
    config: Config,
    builder: PlaylistBuilder,
    limiter,
    job_executor: ThreadPoolExecutor,
) -> Blueprint:
    bp = Blueprint("playlist", __name__)

    # LIMITATION: jobs live in-process — they don't survive restarts and are
    # not shared across gunicorn workers. A client must poll the same worker
    # that accepted its POST (acceptable with current single-instance deploy).
    jobs: dict[str, dict] = {}
    jobs_lock = threading.Lock()

    def _prune_jobs() -> None:
        now = time.time()
        with jobs_lock:
            stale = [
                job_id for job_id, job in jobs.items()
                if job["finished_at"] and now - job["finished_at"] > _JOB_TTL_SECONDS
            ]
            for job_id in stale:
                del jobs[job_id]

    def _run_job(job_id, artists, prefer_original, include_taped, playlist_name, request_id):
        job = jobs[job_id]

        def on_progress(completed, total):
            job["progress"] = {"completed": completed, "total": total}

        try:
            result = builder.build(
                artists, prefer_original, include_taped, playlist_name,
                request_id=request_id, progress_cb=on_progress,
            )
        except RuntimeError as e:
            job.update(state="error", error=str(e), finished_at=time.time())
            return
        except requests.RequestException as e:
            log.error("rid=%s spotify network error: %s", request_id, e)
            job.update(state="error", error=errors.SPOTIFY_NETWORK_ERROR, finished_at=time.time())
            return
        except Exception:
            log.exception("rid=%s unexpected error in playlist job", request_id)
            job.update(state="error", error="internal_error", finished_at=time.time())
            return

        if "error" in result:
            job.update(state="error", error=result["error"], result=result, finished_at=time.time())
        else:
            job.update(state="done", result=result, finished_at=time.time())

    @bp.route("/api/create-playlist", methods=["POST"])
    @limiter.limit("5/minute")
    def create_playlist():
        body    = request.get_json(silent=True) or {}
        artists = body.get("artists", [])

        if not artists:
            return jsonify({"error": errors.NO_ARTISTS}), 400
        if len(artists) > config.max_artists:
            return jsonify({"error": errors.TOO_MANY_ARTISTS}), 400

        artists = [a for a in artists if isinstance(a, dict) and a.get("name", "").strip()]
        if not artists:
            return jsonify({"error": errors.NO_ARTISTS}), 400

        prefer_original = bool(body.get("prefer_original", True))
        include_taped   = bool(body.get("include_taped", False))
        today           = date.today().strftime("%d/%m/%Y")
        playlist_name   = body.get("playlist_name", "").strip() or f"Festival Setlist – {today}"

        _prune_jobs()
        job_id     = uuid.uuid4().hex
        request_id = getattr(g, "request_id", "")
        with jobs_lock:
            jobs[job_id] = {
                "state":       "running",
                "progress":    {"completed": 0, "total": len(artists)},
                "result":      None,
                "error":       None,
                "finished_at": None,
            }
        log.info("rid=%s job=%s queued artists=%d", request_id, job_id, len(artists))
        job_executor.submit(
            _run_job, job_id, artists, prefer_original, include_taped, playlist_name, request_id
        )
        return jsonify({"job_id": job_id}), 202

    @bp.route("/api/playlist-status/<job_id>", methods=["GET"])
    @limiter.exempt
    def playlist_status(job_id):
        job = jobs.get(job_id)
        if job is None:
            return jsonify({"error": errors.JOB_NOT_FOUND}), 404
        return jsonify({
            "state":    job["state"],
            "progress": job["progress"],
            "result":   job["result"],
            "error":    job["error"],
        })

    return bp
