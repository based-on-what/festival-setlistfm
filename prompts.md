# prompts.md — Improvement prompts for festival-setlistfm

Copy-paste prompts to run one at a time. Ordered by priority inside each section.
Each prompt is self-contained and scoped surgically: one concern, verifiable outcome.

---

## 0. Critical fix (do first)

### P0.1 — Fix broken gunicorn entry point

> The Procfile runs `gunicorn app:app --workers 2 --threads 4 --timeout 120`, but `app.py` only defines `create_app()` and an `if __name__ == "__main__"` block — there is no module-level `app` object, so gunicorn fails on deploy. Add `app = create_app()` at module level in `app.py` (guarded so the `__main__` block reuses it instead of calling `create_app()` twice). Verify locally with `gunicorn app:app --check-config` or by running `python -c "from app import app; print(app)"`.

---

## 1. Performance

### P1.1 — Size the HTTP connection pools to match the thread pool

> In `app.py`, `create_app()` builds plain `requests.Session()` objects for `SpotifyClient` and `SetlistFMClient`, but the shared `ThreadPoolExecutor` has 32 workers. The default `HTTPAdapter` pool is 10 connections per host, so under load 22+ threads block waiting for a connection. Mount an `HTTPAdapter(pool_connections=10, pool_maxsize=32)` (sized from `config.thread_pool_workers`) on each session before injecting it. Keep the change inside `create_app()`; do not change client signatures.

### P1.2 — Cache Spotify track search results

> `SpotifyClient.search_track` in `infrastructure/spotify_client.py` hits the Spotify API on every call with no caching. The same (artist, track) pair recurs across requests (popular festival lineups) and within medley fallbacks. Inject a `TTLCache` (already exists in `infrastructure/cache.py`) into `SpotifyClient`, keyed on `(artist_name, track_name)`, TTL ~24h, and cache both hits and misses (cache `None` as a sentinel so missing tracks don't re-query). Wire the cache in `create_app()`. Measure: a repeated create-playlist request for the same lineup should make near-zero Spotify search calls.

### P1.3 — Add retry with backoff for Spotify 429 responses

> `SpotifyClient.search_track` returns `None` on any non-ok response, including 429 rate limits — so under burst load tracks silently go "missing" in playlists. Honor the `Retry-After` header: on 429, sleep up to a small cap (e.g. 2s) and retry once; if still rate limited, return None as today. Apply the same single-retry policy to `add_tracks` failed chunks in the same file. Do not add a retry library; a small inline helper is enough.

### P1.4 — Eliminate nested-executor starvation in the worker pool

> `PlaylistBuilder._collect_tracks` submits `_process_artist` tasks to the shared `ThreadPoolExecutor`, and each of those tasks submits song-resolution tasks to the SAME executor via `TrackResolver.resolve_all`, then blocks on the results. With `max_artists=20` and 32 workers this degrades (20 workers blocked waiting, 12 doing work) and deadlocks outright if `max_artists` is ever raised to ≥32. Split into two executors — a small one for artist-level tasks and one for track resolution — or bound artist-level submissions with a semaphore. Keep dependency injection through `create_app()`. Add a comment documenting the invariant.

### P1.5 — Throttle setlist.fm calls to respect its rate limit

> `SetlistFMClient.get_recent_setlist` pages up to 5 requests per artist, and `PlaylistBuilder` runs up to 20 artists in parallel — up to 100 near-simultaneous setlist.fm calls, while setlist.fm's standard plan allows ~2 req/sec. The current code just aborts the whole request on the first 429. Add a process-wide token-bucket or semaphore-based throttle inside `SetlistFMClient` (configurable rate in `Config`, default 2/sec), so parallel artist processing queues politely instead of triggering 429s.

### P1.6 — Cancel stale artist-search requests in the frontend

> In `static/app.js`, `searchArtists()` has a 350ms debounce but no request cancellation: a slow older response can resolve after a newer one and overwrite the dropdown with stale results. Use an `AbortController` stored at module level — abort the in-flight fetch before starting a new one, and ignore `AbortError` in the catch. No other behavior changes.

---

## 2. Maintenance

### P2.1 — Add a pytest test suite for the backend

> The repo has zero automated tests. Add pytest with: (1) unit tests for `TTLCache` (expiry, thread-safety smoke), `SetlistFMClient._extract_songs` (covers, taped filtering, medley detection, empty names), and `TrackResolver._resolve_song` (cover/prefer_original matrix, medley splitting) using stub clients; (2) route tests for `/api/search-artist` and `/api/create-playlist` using `create_app(Config(...))` with fake clients injected — this requires making `create_app` accept optional pre-built dependencies (keyword-only params defaulting to None), which keeps the factory pattern intact. Mock all HTTP; no live API calls. Add `pytest` to a `requirements-dev.txt`. Target the error-string contracts documented in CLAUDE.md so refactors can't silently break them.

### P2.2 — Pin and audit dependencies

> `requirements.txt` pins flask, requests, python-dotenv and gunicorn but leaves `flask-limiter` unpinned, so deploys are non-reproducible. Pin `flask-limiter` to the currently-installed version (check with `pip show flask-limiter`), and verify the other pins have no known CVEs (`pip audit` or check advisories). Keep the file minimal — do not add transitive pins.

### P2.3 — Centralize error-code strings as constants

> Error strings like `"setlistfm_rate_limited"` and `"spotify_network_error"` are scattered as literals across `infrastructure/setlistfm_client.py`, `infrastructure/spotify_client.py`, `services/playlist_builder.py`, `routes/search.py` and mirrored in `ERROR_MESSAGES` in `static/app.js`. A typo breaks the frontend mapping silently. Create an `errors.py` module with string constants (keep the exact same values — they are an API contract with the frontend), replace backend literals with the constants, and add a test asserting every backend constant has an entry in the frontend catalog (parse `app.js` with a regex in the test, or extract the catalog to a JSON file served to both).

### P2.4 — Fail fast on missing configuration

> `Config.from_env()` in `config.py` silently defaults every credential to `""`; misconfiguration only surfaces at request time as `setlistfm_not_configured`/`spotify_not_configured`. Add a `Config.validate()` method that returns the list of missing variable names, call it in `create_app()`, and log a clear startup warning (do not crash — local dev without keys should still serve the UI). Update CLAUDE.md's env-vars section if behavior text changes.

### P2.5 — Fix the max-artists copy mismatch

> CLAUDE.md notes the placeholder in `templates/index.html` says "Up to 10" while `Config.max_artists` is 20. Make the limit single-source: render the template with `max_artists` passed from config in the `index()` route (`render_template("index.html", max_artists=config.max_artists)`) and interpolate it in the placeholder and any helper text. Check `static/app.js` and `index.html` for other hardcoded "10"/"20" copies.

### P2.6 — Add structured request logging

> Backend logs (`playlist_builder.py`, `routes/playlist.py`) have no request correlation — concurrent create-playlist requests interleave indistinguishably. Add a per-request ID (short uuid) via a Flask `before_request` hook stored on `g`, include it in route-level log lines, and pass it into `PlaylistBuilder.build` logs. Keep stdlib logging; no new dependencies.

### P2.7 — Add a healthcheck endpoint

> Railway and uptime monitors need a cheap liveness probe; today the only GET route renders the full SPA. Add `GET /healthz` in `app.py` returning `{"status": "ok"}` with no auth, no rate-limit counting (`@limiter.exempt`), and no external API calls.

---

## 3. Scalability

### P3.1 — Make rate limiting work across gunicorn workers

> Flask-Limiter in `app.py` uses its default in-memory storage. With `--workers 2` in the Procfile each worker keeps its own counters, so real limits are double the configured ones, and they reset on every deploy. Document this as a known limitation in CLAUDE.md, and make the storage backend configurable via env var (`RATELIMIT_STORAGE_URI`, e.g. a Railway Redis URL), falling back to in-memory for local dev. Flask-Limiter supports `storage_uri` natively — no custom code needed.

### P3.2 — Bound the TTLCache memory

> `TTLCache` in `infrastructure/cache.py` never evicts: expired entries stay in the dict forever and there is no max size, so a long-running worker grows unboundedly (every searched artist/setlist key accumulates). Add `max_entries` (default ~1000) with simple eviction: on `set`, if over the limit, drop expired entries first, then oldest-expiry entries. Keep the lock discipline and the existing public API (`get`/`set`) unchanged — `setlistfm_client.py` and any future callers must not need edits.

### P3.3 — Move playlist creation to a background job with progress polling

> `POST /api/create-playlist` does all the work synchronously: 100 artists × setlist paging × track resolution × playlist writes inside one request, relying on gunicorn's 120s timeout. This caps throughput at workers×threads (8 concurrent requests) and gives the user zero progress feedback. Refactor to a job model: the POST enqueues a job (in-process dict of job-id → state, since there's no Redis yet), returns `202 {"job_id": ...}`, work runs on the existing executor, and a new `GET /api/playlist-status/<job_id>` returns `{"state": "running"|"done"|"error", "progress": {...}, "result": {...}}`. Update `static/app.js` `createPlaylist()` to poll every 2s and show per-artist progress. Keep the old synchronous response shape inside `result` so `showResult()` needs minimal changes. Note the limitation: in-process jobs don't survive restarts and aren't shared across workers — sticky behavior is acceptable for now; document it.

### P3.4 — Deduplicate tracks across artists

> `PlaylistBuilder.build` concatenates `all_track_ids` with no dedup — two artists covering the same song, or a shared festival anthem, lands twice in the playlist, wasting Spotify API quota in `add_tracks` and bloating playlists as lineups grow. Dedupe while preserving first-occurrence order (`dict.fromkeys`) before calling `add_tracks`, and report `duplicates_removed` in the response. Frontend: ignore the new field for now (additive change).

### P3.5 — Add per-request timeout budget to PlaylistBuilder

> Worst case today: 100 artists × 5 setlist pages × 8s timeout each, plus track resolution — easily exceeding the 120s gunicorn timeout, which kills the request after the playlist may already be created on Spotify (orphan playlists). Add a deadline to `PlaylistBuilder.build` (e.g. 90s from start, configurable in `Config`): pass remaining-time down so `_collect_tracks` futures use `future.result(timeout=remaining)`; artists that miss the deadline get status `"timeout"` and the playlist is built from what resolved. Add `"timeout"` handling to the frontend summary in `showResult()`.

### P3.6 — Serve static assets with cache headers

> Flask serves `static/` with default caching (no immutable hints), so every visit re-validates `style.css` (~20KB), `app.js` and components — wasted RTT at scale and slower loads. Set `SEND_FILE_MAX_AGE_DEFAULT` (e.g. 1 hour) in `create_app()` and add a cache-busting query param (`?v=<version>`) to the script/style tags in `templates/index.html`, with the version string defined in one place (config or a constant in `app.py`). No bundler — keep it that simple.

---

## Suggested order

1. **P0.1** (deploy is broken without it)
2. **P2.1** (tests — everything after this is safer)
3. **P1.1, P1.4, P1.5** (the concurrency trio — same subsystem, do together or in sequence)
4. **P1.2, P1.3** (Spotify efficiency)
5. **P3.2, P3.1** (memory + rate-limit correctness)
6. **P2.2–P2.7** (maintenance batch, each independent)
7. **P3.4, P3.6, P1.6** (small wins, independent)
8. **P3.3, P3.5** (biggest refactor last, with tests already in place)
